-- Crear base de datos (puedes cambiar el nombre si quieres)
CREATE DATABASE IF NOT EXISTS cerveceria_produccion
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE cerveceria_produccion;

-- ============================
-- TABLA BASE: MATERIA PRIMA
-- ============================
CREATE TABLE materia_prima (
    id_materia_prima INT AUTO_INCREMENT PRIMARY KEY,
    nombre           VARCHAR(100) NOT NULL,
    tipo             ENUM('MALTA','LUPULO','LEVADURA','OTRO') NOT NULL,
    fabricante       VARCHAR(100),
    origen           VARCHAR(100),        -- país / región
    unidad_base      ENUM('KG','G','L','ML','UNIDAD') NOT NULL,
    notas            TEXT,
    activo           TINYINT(1) DEFAULT 1
) ENGINE=InnoDB;

-- ============================
-- DETALLE LEVADURAS
-- ============================
CREATE TABLE levadura_detalle (
    id_materia_prima INT PRIMARY KEY,
    tipo_levadura    ENUM('ALE','LAGER','KVEIK','HIBRIDA','OTRA') DEFAULT 'OTRA',
    forma            ENUM('SECA','LIQUIDA') DEFAULT 'SECA',
    floculacion      ENUM('BAJA','MEDIA','ALTA') NOT NULL,
    atenuacion_min   TINYINT,    -- % mínimo
    atenuacion_max   TINYINT,    -- % máximo
    pitch_rate_mill_cel_ml_plato DECIMAL(6,2), -- millones de células / ml / °P
    temperatura_min_c TINYINT,   -- rango en °C
    temperatura_max_c TINYINT,
    notas_estilo     TEXT,
    CONSTRAINT fk_levadura_mp
      FOREIGN KEY (id_materia_prima)
      REFERENCES materia_prima(id_materia_prima)
      ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB;

-- ============================
-- DETALLE LÚPULOS
-- ============================
CREATE TABLE lupulo_detalle (
    id_materia_prima INT PRIMARY KEY,
    uso              ENUM('AMARGOR','AROMA','DUAL') DEFAULT 'DUAL',
    forma            ENUM('PELLET','FLOR','EXTRACTO') DEFAULT 'PELLET',
    alfa_acidos_pct  DECIMAL(5,2),    -- %
    beta_acidos_pct  DECIMAL(5,2),    -- %
    cohumulona_pct   DECIMAL(5,2),    -- opcional
    aceites_totales_ml_100g DECIMAL(5,2), -- ml / 100 g
    perfil_aroma     VARCHAR(200),    -- cítrico, resinoso, frutal, tropical, etc.
    año_cosecha      YEAR,
    CONSTRAINT fk_lupulo_mp
      FOREIGN KEY (id_materia_prima)
      REFERENCES materia_prima(id_materia_prima)
      ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB;

-- ============================
-- DETALLE MALTAS
-- ============================
CREATE TABLE malta_detalle (
    id_materia_prima INT PRIMARY KEY,
    tipo_malta       ENUM('BASE','CARAMELO','TOSTADA','ESPECIAL','OTRA') DEFAULT 'BASE',
    color_ebc        DECIMAL(6,2),    -- EBC
    color_lovibond   DECIMAL(6,2),    -- si quieres ambos
    potencial_gravedad DECIMAL(6,3),  -- ej: 1.036, 1.038
    proteinas_pct    DECIMAL(5,2),
    ph_mosto_color   DECIMAL(4,2),    -- pH típico con esa malta
    uso_max_pct_molienda DECIMAL(5,2),-- % máximo recomendado en la molienda
    CONSTRAINT fk_malta_mp
      FOREIGN KEY (id_materia_prima)
      REFERENCES materia_prima(id_materia_prima)
      ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB;

-- ============================
-- LOTES DE MATERIA PRIMA
-- ============================
CREATE TABLE lote_materia_prima (
    id_lote          INT AUTO_INCREMENT PRIMARY KEY,
    id_materia_prima INT NOT NULL,
    codigo_lote      VARCHAR(100) NOT NULL,
    fecha_compra     DATE,
    proveedor        VARCHAR(150),
    cantidad_inicial DECIMAL(10,3) NOT NULL,
    cantidad_disponible DECIMAL(10,3) NOT NULL,
    costo_unitario   DECIMAL(10,2),
    fecha_vencimiento DATE,
    notas            TEXT,
    CONSTRAINT fk_lote_materia
        FOREIGN KEY (id_materia_prima) REFERENCES materia_prima(id_materia_prima)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    UNIQUE KEY uk_lote_cod (codigo_lote, id_materia_prima)
) ENGINE=InnoDB;
