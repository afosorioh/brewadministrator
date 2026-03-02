USE cerveceria_produccion;

CREATE TABLE IF NOT EXISTS receta (
    id_receta               INT AUTO_INCREMENT PRIMARY KEY,
    nombre                  VARCHAR(100) NOT NULL,
    estilo                  VARCHAR(100),
    descripcion             TEXT,
    volumen_estandar_litros DECIMAL(10,2)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS bache (
    id_bache                INT AUTO_INCREMENT PRIMARY KEY,
    codigo_bache            VARCHAR(100) NOT NULL,
    nombre_cerveza          VARCHAR(100) NOT NULL,
    id_receta               INT NULL,
    fecha_coccion           DATE NOT NULL,
    volumen_objetivo_litros DECIMAL(10,2),
    volumen_final_litros    DECIMAL(10,2),
    densidad_inicial        DECIMAL(6,3),
    densidad_final          DECIMAL(6,3),
    estado                  ENUM('PLANIFICADO','EN_CURSO','FERMENTANDO','MADURANDO','LISTO','COMPLETADO','DESCARTADO')
                            DEFAULT 'PLANIFICADO',
    notas                   TEXT,
    CONSTRAINT fk_bache_receta
        FOREIGN KEY (id_receta) REFERENCES receta(id_receta)
        ON UPDATE CASCADE ON DELETE SET NULL,
    UNIQUE KEY uk_bache_codigo (codigo_bache)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS bache_materia_prima (
    id_bache_materia  INT AUTO_INCREMENT PRIMARY KEY,
    id_bache          INT NOT NULL,
    id_lote           INT NOT NULL,   -- lote_materia_prima
    cantidad_usada    DECIMAL(10,3) NOT NULL,
    unidad            ENUM('KG','G','L','ML','UNIDAD') NOT NULL,

    -- NUEVO: información de proceso / etapa
    etapa_proceso     ENUM('MACERACION','HERVOR','WHIRLPOOL','FERMENTACION','MADURACION','OTRA')
                      NOT NULL DEFAULT 'OTRA',

    -- NUEVO: cómo se usa ese insumo en esa etapa
    tipo_aplicacion   ENUM('GENERAL','AMARGOR','SABOR','AROMA','DRY_HOP','NUTRIENTE','OTRA')
                      NOT NULL DEFAULT 'GENERAL',

    -- NUEVO: tiempo relativo para hervido / whirlpool
    tiempo_minutos_desde_inicio_hervor INT NULL,

    -- NUEVO: tiempo relativo para fermentación (ej. dry hop a día 3)
    dias_desde_inicio_fermentacion INT NULL,

    notas             TEXT,

    CONSTRAINT fk_bmp_bache
        FOREIGN KEY (id_bache) REFERENCES bache(id_bache)
        ON UPDATE CASCADE ON DELETE CASCADE,

    CONSTRAINT fk_bmp_lote
        FOREIGN KEY (id_lote) REFERENCES lote_materia_prima(id_lote)
        ON UPDATE CASCADE ON DELETE RESTRICT,

    INDEX idx_bmp_bache (id_bache),
    INDEX idx_bmp_proceso (etapa_proceso, tipo_aplicacion)
) ENGINE=InnoDB;

ALTER TABLE lote_materia_prima
    ADD COLUMN generacion_actual TINYINT DEFAULT 0;

CREATE TABLE IF NOT EXISTS bache_levadura_uso (
    id_bache_levadura INT AUTO_INCREMENT PRIMARY KEY,
    id_bache          INT NOT NULL,
    id_lote           INT NOT NULL,   -- debe ser un lote de tipo LEVADURA

    tipo_uso          ENUM('NUEVA','REUTILIZADA') NOT NULL,

    -- generacion = 0 si es lote nuevo / primer uso
    generacion        TINYINT NOT NULL DEFAULT 0,

    -- bache del que se recuperó la levadura (si aplica)
    id_bache_origen   INT NULL,

    fecha_inoculacion DATETIME,
    comentarios       TEXT,

    CONSTRAINT fk_blev_bache
        FOREIGN KEY (id_bache) REFERENCES bache(id_bache)
        ON UPDATE CASCADE ON DELETE CASCADE,

    CONSTRAINT fk_blev_lote
        FOREIGN KEY (id_lote) REFERENCES lote_materia_prima(id_lote)
        ON UPDATE CASCADE ON DELETE RESTRICT,

    CONSTRAINT fk_blev_bache_origen
        FOREIGN KEY (id_bache_origen) REFERENCES bache(id_bache)
        ON UPDATE CASCADE ON DELETE SET NULL,

    INDEX idx_blev_bache (id_bache),
    INDEX idx_blev_lote (id_lote)
) ENGINE=InnoDB;
