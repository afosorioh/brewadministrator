-- Usar la base de datos
USE cerveceria_produccion;

-- ============================
-- 1) TIPOS DE BARRIL
-- ============================
CREATE TABLE IF NOT EXISTS tipo_barril (
    id_tipo_barril   INT AUTO_INCREMENT PRIMARY KEY,
    capacidad_litros DECIMAL(10,2) NOT NULL,
    descripcion      VARCHAR(100)
) ENGINE=InnoDB;

-- Opcional: tipos estándar de barril
INSERT INTO tipo_barril (capacidad_litros, descripcion) VALUES
(20.0, 'Barril 20 L'),
(30.0, 'Barril 30 L'),
(50.0, 'Barril 50 L');

-- ============================
-- 2) BARRILES
-- ============================
CREATE TABLE IF NOT EXISTS barril (
    id_barril      INT AUTO_INCREMENT PRIMARY KEY,
    codigo_barril  VARCHAR(100) NOT NULL,    -- código físico/etiqueta
    id_tipo_barril INT NOT NULL,
    fecha_ingreso  DATE,
    estado_actual  ENUM('NUEVO','VACIO','LLENO','EN_CLIENTE','FUERA_SERVICIO')
                   DEFAULT 'NUEVO',
    notas          TEXT,
    CONSTRAINT fk_barril_tipo
        FOREIGN KEY (id_tipo_barril)
        REFERENCES tipo_barril(id_tipo_barril)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    UNIQUE KEY uk_barril_codigo (codigo_barril)
) ENGINE=InnoDB;

-- ============================
-- 3) CLIENTES (para salidas de barriles)
-- ============================
CREATE TABLE IF NOT EXISTS cliente (
    id_cliente  INT AUTO_INCREMENT PRIMARY KEY,
    nombre      VARCHAR(150) NOT NULL,
    tipo        ENUM('BAR','RESTAURANTE','EVENTO','TAPROOM_INTERNO','OTRO')
                DEFAULT 'OTRO',
    contacto    VARCHAR(150),
    telefono    VARCHAR(50),
    direccion   VARCHAR(200),
    activo      TINYINT(1) DEFAULT 1
) ENGINE=InnoDB;

-- ============================
-- 4) MOVIMIENTOS DE BARRILES
-- ============================
-- Historial: ingreso, llenado, salida, retorno, baja, mantenimiento
-- Nota: bache.id_bache ya debe existir (parte 2)
CREATE TABLE IF NOT EXISTS movimiento_barril (
    id_movimiento   INT AUTO_INCREMENT PRIMARY KEY,
    id_barril       INT NOT NULL,
    fecha_hora      DATETIME NOT NULL,
    tipo_movimiento ENUM('INGRESO','LLENADO','SALIDA_CLIENTE',
                         'RETORNO_VACIO','BAJA','MANTENIMIENTO') NOT NULL,

    -- Llenado: de qué bache salió la cerveza
    id_bache        INT NULL,

    -- Salida a cliente: a quién se va el barril
    id_cliente      INT NULL,

    -- Volumen real del movimiento (ej. litros llenados)
    volumen_litros  DECIMAL(10,2),

    comentario      TEXT,

    CONSTRAINT fk_mov_barril
        FOREIGN KEY (id_barril)
        REFERENCES barril(id_barril)
        ON UPDATE CASCADE ON DELETE CASCADE,

    CONSTRAINT fk_mov_bache
        FOREIGN KEY (id_bache)
        REFERENCES bache(id_bache)
        ON UPDATE CASCADE ON DELETE SET NULL,

    CONSTRAINT fk_mov_cliente
        FOREIGN KEY (id_cliente)
        REFERENCES cliente(id_cliente)
        ON UPDATE CASCADE ON DELETE SET NULL,

    INDEX idx_mov_barril (id_barril, fecha_hora),
    INDEX idx_mov_tipo (tipo_movimiento),
    INDEX idx_mov_bache (id_bache)
) ENGINE=InnoDB;
