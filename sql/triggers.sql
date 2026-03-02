USE cerveceria_produccion;

DELIMITER $$

CREATE TRIGGER trg_blev_before_insert
BEFORE INSERT ON bache_levadura_uso
FOR EACH ROW
BEGIN
    DECLARE gen_actual TINYINT DEFAULT 0;

    -- Obtenemos la generación actual del lote
    SELECT IFNULL(generacion_actual, 0)
      INTO gen_actual
      FROM lote_materia_prima
     WHERE id_lote = NEW.id_lote;

    IF NEW.tipo_uso = 'NUEVA' THEN
        -- Primera vez que se usa este lote como pitch
        SET NEW.generacion = 0;
        UPDATE lote_materia_prima
           SET generacion_actual = 0
         WHERE id_lote = NEW.id_lote;
    ELSE
        -- REUTILIZADA: aumentamos generación
        SET NEW.generacion = gen_actual + 1;
        UPDATE lote_materia_prima
           SET generacion_actual = NEW.generacion
         WHERE id_lote = NEW.id_lote;
    END IF;
END$$

DELIMITER ;
