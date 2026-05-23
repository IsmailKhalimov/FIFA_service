"""
Одноразовая загрузка портретов игроков в S3 и запись публичного URL в `player.photo_url`.

Источники по порядку:
1. Sports.ru
2. Wikipedia

Если фото не найдено, `photo_url` остаётся пустым, а фронт показывает дефолтную иконку.

Запуск из корня репозитория:
  pip install -r requirements.txt
  python tools/upload_player_photos_to_s3.py
  python tools/upload_player_photos_to_s3.py --dry-run
  python tools/upload_player_photos_to_s3.py --limit 10
  python tools/upload_player_photos_to_s3.py --overwrite-existing
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

# корень проекта -> import src
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import boto3  # noqa: E402
import psycopg2  # noqa: E402
from botocore.exceptions import BotoCoreError, ClientError  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

from config import get_database_settings  # noqa: E402
from tm_images import fetch_player_portrait_bytes_with_report  # noqa: E402

load_dotenv(ROOT / ".env")


def _public_object_url(bucket: str, region: str, key: str, base_override: str | None) -> str:
    if base_override:
        return f"{base_override.rstrip('/')}/{key}"
    if region == "us-east-1":
        return f"https://{bucket}.s3.amazonaws.com/{key}"
    return f"https://{bucket}.s3.{region}.amazonaws.com/{key}"


def _guess_image_extension(data: bytes) -> tuple[str, str]:
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg", "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png", "image/png"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "webp", "image/webp"
    return "jpg", "image/jpeg"


def _load_player_rows(cur, *, free_agents_only: bool, overwrite_existing: bool) -> list[tuple]:
    conditions: list[str] = []
    if free_agents_only:
        conditions.append("p.club_id IS NULL")
    if not overwrite_existing:
        conditions.append("(p.photo_url IS NULL OR p.photo_url = '')")

    where_sql = ""
    if conditions:
        where_sql = "WHERE " + " AND ".join(conditions)

    cur.execute(
        f"""
        SELECT p.player_id, p.name, p.club_id, p.photo_url
        FROM player p
        {where_sql}
        ORDER BY p.player_id;
        """
    )
    return cur.fetchall()


def _print_report(report: list[dict[str, str]]) -> None:
    for item in report:
        source = item.get("source", "unknown")
        status = item.get("status", "unknown")
        message = item.get("message", "")
        url = item.get("url", "")
        print(f"\n    - {source}: {status} - {message}", end="")
        if url:
            print(f"\n      URL: {url}", end="")


def main() -> None:
    parser = argparse.ArgumentParser(description="Загрузка фото игроков в S3")
    parser.add_argument("--dry-run", action="store_true", help="Не писать в S3 и БД")
    parser.add_argument("--limit", type=int, default=0, help="Максимум игроков (0 = все)")
    parser.add_argument(
        "--free-agents-only",
        action="store_true",
        help="Обработать только свободных агентов (club_id IS NULL)",
    )
    parser.add_argument(
        "--overwrite-existing",
        action="store_true",
        help="Перезаписывать игроков, у которых photo_url уже заполнен",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.8,
        help="Пауза между игроками в секундах (по умолчанию 0.8)",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Печатать подробный отчёт по каждому игроку и источнику",
    )
    args = parser.parse_args()

    bucket = os.environ.get("S3_BUCKET") or os.environ.get("AWS_S3_BUCKET")
    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "eu-central-1"
    public_base = os.environ.get("S3_PUBLIC_BASE_URL")

    if not bucket and not args.dry_run:
        print("Задайте S3_BUCKET (или AWS_S3_BUCKET) в .env")
        sys.exit(1)
    if args.dry_run and not bucket:
        bucket = "your-bucket"

    ak = os.environ.get("AWS_ACCESS_KEY_ID")
    sk = os.environ.get("AWS_SECRET_ACCESS_KEY")
    endpoint = os.environ.get("S3_ENDPOINT_URL")

    s3 = None
    if not args.dry_run:
        session = boto3.session.Session(
            aws_access_key_id=ak,
            aws_secret_access_key=sk,
            region_name=region,
        )
        s3 = session.client("s3", endpoint_url=endpoint or None)

    db = get_database_settings()
    conn_kw = {
        "dbname": db["dbname"],
        "user": db["user"],
        "password": db["password"],
        "host": db["host"],
        "port": db["port"],
    }
    if db.get("sslmode"):
        conn_kw["sslmode"] = db["sslmode"]

    conn = psycopg2.connect(**conn_kw)
    cur = conn.cursor()
    rows = _load_player_rows(
        cur,
        free_agents_only=args.free_agents_only,
        overwrite_existing=args.overwrite_existing,
    )
    if args.limit > 0:
        rows = rows[: args.limit]

    ok, fail, skipped = 0, 0, 0
    by_source = {"Sports.ru": 0, "Wikipedia": 0}

    for player_id, name, club_id, photo_url in rows:
        status = "FA" if club_id is None else f"club={club_id}"
        existing = " with photo" if photo_url else ""
        print(f"[{player_id}] {name} ({status}{existing})...", end=" ", flush=True)

        if args.delay > 0:
            time.sleep(args.delay)

        data, source, report = fetch_player_portrait_bytes_with_report(name)
        if not data or len(data) < 100:
            print("фото не найдено")
            if args.report:
                _print_report(report)
                print()
            skipped += 1
            continue

        ext, content_type = _guess_image_extension(data)
        key = f"players/{player_id}.{ext}"
        url = _public_object_url(bucket, region, key, public_base)

        if args.dry_run:
            print(f"dry-run -> {source} -> {url}")
            if args.report:
                _print_report(report)
                print()
            if source in by_source:
                by_source[source] += 1
            ok += 1
            continue

        assert s3 is not None and bucket
        try:
            s3.put_object(
                Bucket=bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
                CacheControl="max-age=31536000,public",
            )
        except (ClientError, BotoCoreError) as exc:
            print(f"ошибка S3: {exc}")
            fail += 1
            continue

        cur.execute(
            "UPDATE player SET photo_url = %s WHERE player_id = %s",
            (url, player_id),
        )
        conn.commit()
        print(f"OK ({source}) -> {url}")
        if args.report:
            _print_report(report)
            print()
        if source in by_source:
            by_source[source] += 1
        ok += 1

    cur.close()
    conn.close()

    print(f"Готово: успешно {ok}, ошибок {fail}, без фото {skipped}")
    print(
        "Источник фото: "
        f"Sports.ru={by_source['Sports.ru']}, "
        f"Wikipedia={by_source['Wikipedia']}"
    )


if __name__ == "__main__":
    main()
