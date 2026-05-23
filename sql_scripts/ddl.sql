-- Таблица стран
CREATE TABLE Country (
    country_id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    region VARCHAR(255)
);

COMMENT ON TABLE Country IS 'Информация о странах, связанных с клубами и городами';
COMMENT ON COLUMN Country.country_id IS 'Уникальный идентификатор страны';
COMMENT ON COLUMN Country.name IS 'Название страны';
COMMENT ON COLUMN Country.region IS 'Регион, к которому относится страна';

-- Таблица городов
CREATE TABLE City (
    city_id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    country_id INT NOT NULL REFERENCES Country(country_id)
);

COMMENT ON TABLE City IS 'Информация о городах, связанных с странами и стадионами';
COMMENT ON COLUMN City.city_id IS 'Уникальный идентификатор города';
COMMENT ON COLUMN City.name IS 'Название города';
COMMENT ON COLUMN City.country_id IS 'Идентификатор страны, к которой относится город';

-- Таблица стадионов
CREATE TABLE Stadium (
    stadium_id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    type_of_pitch VARCHAR(255),
    city_id INT NOT NULL REFERENCES City(city_id)
);

COMMENT ON TABLE Stadium IS 'Информация о стадионах, на которых играют футбольные клубы';
COMMENT ON COLUMN Stadium.stadium_id IS 'Уникальный идентификатор стадиона';
COMMENT ON COLUMN Stadium.name IS 'Название стадиона';
COMMENT ON COLUMN Stadium.type_of_pitch IS 'Тип покрытия стадиона (например, трава или искусственный газон)';
COMMENT ON COLUMN Stadium.city_id IS 'Идентификатор города, в котором расположен стадион';

-- Таблица клубов
CREATE TABLE Club (
    club_id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    stadium_id INT REFERENCES Stadium(stadium_id),
    rating INT CHECK (rating BETWEEN 0 AND 100)
);

COMMENT ON TABLE Club IS 'Информация о футбольных клубах, их стадионах и рейтингах';
COMMENT ON COLUMN Club.club_id IS 'Уникальный идентификатор клуба';
COMMENT ON COLUMN Club.name IS 'Название клуба';
COMMENT ON COLUMN Club.stadium_id IS 'Идентификатор стадиона, на котором играет клуб';
COMMENT ON COLUMN Club.rating IS 'Рейтинг клуба в диапазоне от 0 до 100';

-- Справочник подклассов игроков (уточнение роли внутри амплуа)
CREATE TABLE player_subtype (
    subtype_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    position_category VARCHAR(50) NOT NULL,
    UNIQUE (name, position_category)
);

COMMENT ON TABLE player_subtype IS 'Подклассы игроков (тактический тип внутри позиции)';
COMMENT ON COLUMN player_subtype.subtype_id IS 'Идентификатор подкласса';
COMMENT ON COLUMN player_subtype.name IS 'Название подкласса';
COMMENT ON COLUMN player_subtype.position_category IS 'Амплуа: Вратарь, Защитник, Полузащитник или Нападающий';

-- Таблица игроков
CREATE TABLE Player (
    player_id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    age INT CHECK (age > 0),
    salary NUMERIC(10, 2) CHECK (salary >= 0),
    subtype_id INT NOT NULL REFERENCES player_subtype(subtype_id),
    photo_url VARCHAR(512),
    transfermarkt_player_id INTEGER,
    club_id INT REFERENCES Club(club_id),
    nationality_country_id INT NOT NULL REFERENCES Country(country_id),
    goals_last_season INT NOT NULL DEFAULT 0 CHECK (goals_last_season >= 0),
    assists_last_season INT NOT NULL DEFAULT 0 CHECK (assists_last_season >= 0)
);

COMMENT ON TABLE Player IS 'Информация об игроках, их клубах и заработной плате';
COMMENT ON COLUMN Player.player_id IS 'Уникальный идентификатор игрока';
COMMENT ON COLUMN Player.name IS 'Имя игрока';
COMMENT ON COLUMN Player.age IS 'Возраст игрока';
COMMENT ON COLUMN Player.salary IS 'Заработная плата игрока';
COMMENT ON COLUMN Player.subtype_id IS 'Подкласс игрока (FK на player_subtype)';
COMMENT ON COLUMN Player.photo_url IS 'URL изображения игрока (ручное переопределение)';
COMMENT ON COLUMN Player.transfermarkt_player_id IS 'ID игрока на transfermarkt.com для загрузки официального портрета';
COMMENT ON COLUMN Player.club_id IS 'Идентификатор клуба, в котором играет игрок (NULL — свободный агент)';
COMMENT ON COLUMN Player.nationality_country_id IS 'Страна гражданства игрока (FK на Country; без дублирования названия в Player — 3НФ)';
COMMENT ON COLUMN Player.goals_last_season IS 'Голы за последний завершённый сезон (не карьера)';
COMMENT ON COLUMN Player.assists_last_season IS 'Голевые передачи за последний завершённый сезон (не карьера)';

-- Таблица трофеев
CREATE TABLE Trophy (
    trophy_id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    prize_fund NUMERIC(10, 2) CHECK (prize_fund >= 0)
);

COMMENT ON TABLE Trophy IS 'Информация о трофеях, разыгрываемых в футбольных турнирах';
COMMENT ON COLUMN Trophy.trophy_id IS 'Уникальный идентификатор трофея';
COMMENT ON COLUMN Trophy.name IS 'Название трофея';
COMMENT ON COLUMN Trophy.prize_fund IS 'Призовой фонд трофея';

-- Связь клубов с трофеями
CREATE TABLE Club_Trophy (
    club_id INT NOT NULL REFERENCES Club(club_id),
    trophy_id INT NOT NULL REFERENCES Trophy(trophy_id),
    year_won INT CHECK (year_won > 0),
    PRIMARY KEY (club_id, trophy_id, year_won)
);

COMMENT ON TABLE Club_Trophy IS 'Информация о завоёванных клубами трофеях';
COMMENT ON COLUMN Club_Trophy.club_id IS 'Идентификатор клуба, который выиграл трофей';
COMMENT ON COLUMN Club_Trophy.trophy_id IS 'Идентификатор трофея, выигранного клубом';
COMMENT ON COLUMN Club_Trophy.year_won IS 'Год, когда клуб выиграл трофей';

-- Таблица пользователей
CREATE TABLE Users (
    user_id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role VARCHAR(10) DEFAULT 'user'
);

-- Комментарии для таблицы и её столбцов
COMMENT ON TABLE Users IS 'Информация о пользователях системы';
COMMENT ON COLUMN Users.user_id IS 'Уникальный идентификатор пользователя';
COMMENT ON COLUMN Users.username IS 'Имя пользователя, уникальное в системе';
COMMENT ON COLUMN Users.password IS 'Хэшированный пароль пользователя';
COMMENT ON COLUMN Users.role IS 'Роль пользователя в системе (user или admin)';
