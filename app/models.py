from app.extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

class Rol(db.Model):
    __tablename__ = "rol"
    id = db.Column("id_rol", db.Integer, primary_key=True)
    nombre = db.Column(db.Enum("ADMIN", "GESTOR", "SUPERVISOR", name="rol_nombre"), unique=True, nullable=False)

    usuarios = db.relationship("Usuario", back_populates="rol", lazy="dynamic")

class Usuario(UserMixin, db.Model):
    __tablename__ = "usuario"

    id = db.Column("id_usuario", db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    activo = db.Column(db.Boolean, default=True, nullable=False)

    id_rol = db.Column(db.Integer, db.ForeignKey("rol.id_rol", ondelete="RESTRICT"), nullable=False)

    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    actualizado_en = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    rol = db.relationship("Rol", back_populates="usuarios")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    # Flask-Login usa esto para permitir login
    def is_active(self):
        return self.activo
    
class MateriaPrima(db.Model):
    __tablename__ = "materia_prima"

    id = db.Column("id_materia_prima", db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    tipo = db.Column(
        db.Enum("MALTA", "LUPULO", "LEVADURA", "OTRO", name="tipo_materia_prima"),
        nullable=False,
    )
    fabricante = db.Column(db.String(100))
    origen = db.Column(db.String(100))
    unidad_base = db.Column(
        db.Enum("KG", "G", "L", "ML", "UNIDAD", name="unidad_base_materia"),
        nullable=False,
    )
    notas = db.Column(db.Text)
    activo = db.Column(db.Boolean, default=True)

    # Relaciones
    levadura_detalle = db.relationship(
        "LevaduraDetalle", back_populates="materia_prima", uselist=False
    )
    lupulo_detalle = db.relationship(
        "LupuloDetalle", back_populates="materia_prima", uselist=False
    )
    malta_detalle = db.relationship(
        "MaltaDetalle", back_populates="materia_prima", uselist=False
    )
    otros_detalle = db.relationship(
        "OtrosMtpDetalle", back_populates="materia_prima", uselist=False
    )
    lotes = db.relationship(
        "LoteMateriaPrima", back_populates="materia_prima", lazy="dynamic"
    )

    def __repr__(self):
        return f"<MateriaPrima {self.id} {self.nombre} ({self.tipo})>"


class LevaduraDetalle(db.Model):
    __tablename__ = "levadura_detalle"

    id_materia_prima = db.Column(
        db.Integer,
        db.ForeignKey("materia_prima.id_materia_prima", ondelete="CASCADE"),
        primary_key=True,
    )

    tipo_levadura = db.Column(
        db.Enum("ALE", "LAGER", "KVEIK", "HIBRIDA", "OTRA", name="tipo_levadura"),
        default="OTRA",
    )
    forma = db.Column(
        db.Enum("SECA", "LIQUIDA", name="forma_levadura"), default="SECA"
    )
    floculacion = db.Column(
        db.Enum("BAJA", "MEDIA", "ALTA", name="floculacion_levadura"),
        nullable=False,
    )
    atenuacion_min = db.Column(db.SmallInteger)
    atenuacion_max = db.Column(db.SmallInteger)
    pitch_rate_mill_cel_ml_plato = db.Column(db.Numeric(6, 2))
    temperatura_min_c = db.Column(db.SmallInteger)
    temperatura_max_c = db.Column(db.SmallInteger)
    notas_estilo = db.Column(db.Text)

    materia_prima = db.relationship(
        "MateriaPrima", back_populates="levadura_detalle", uselist=False
    )

    def __repr__(self):
        return f"<LevaduraDetalle MP:{self.id_materia_prima}>"


class LupuloDetalle(db.Model):
    __tablename__ = "lupulo_detalle"

    id_materia_prima = db.Column(
        db.Integer,
        db.ForeignKey("materia_prima.id_materia_prima", ondelete="CASCADE"),
        primary_key=True,
    )

    uso = db.Column(
        db.Enum("AMARGOR", "AROMA", "DUAL", name="uso_lupulo"), default="DUAL"
    )
    forma = db.Column(
        db.Enum("PELLET", "FLOR", "EXTRACTO", name="forma_lupulo"), default="PELLET"
    )
    alfa_acidos_pct = db.Column(db.Numeric(5, 2))
    beta_acidos_pct = db.Column(db.Numeric(5, 2))
    cohumulona_pct = db.Column(db.Numeric(5, 2))
    aceites_totales_ml_100g = db.Column(db.Numeric(5, 2))
    perfil_aroma = db.Column(db.String(200))
    año_cosecha = db.Column(db.Integer)  # YEAR también se puede mapear como Integer

    materia_prima = db.relationship(
        "MateriaPrima", back_populates="lupulo_detalle", uselist=False
    )

    def __repr__(self):
        return f"<LupuloDetalle MP:{self.id_materia_prima}>"


class MaltaDetalle(db.Model):
    __tablename__ = "malta_detalle"

    id_materia_prima = db.Column(
        db.Integer,
        db.ForeignKey("materia_prima.id_materia_prima", ondelete="CASCADE"),
        primary_key=True,
    )

    tipo_malta = db.Column(
        db.Enum(
            "BASE", "CARAMELO", "TOSTADA", "ESPECIAL", "OTRA", name="tipo_malta"
        ),
        default="BASE",
    )
    color_ebc = db.Column(db.Numeric(6, 2))
    color_lovibond = db.Column(db.Numeric(6, 2))
    potencial_gravedad = db.Column(db.Numeric(6, 3))
    proteinas_pct = db.Column(db.Numeric(5, 2))
    ph_mosto_color = db.Column(db.Numeric(4, 2))
    uso_max_pct_molienda = db.Column(db.Numeric(5, 2))

    materia_prima = db.relationship(
        "MateriaPrima", back_populates="malta_detalle", uselist=False
    )

    def __repr__(self):
        return f"<MaltaDetalle MP:{self.id_materia_prima}>"

class OtrosMtpDetalle(db.Model):
    __tablename__ = "otros_mtp_detalle"

    id_materia_prima = db.Column(
        db.Integer,
        db.ForeignKey("materia_prima.id_materia_prima", ondelete="CASCADE"),
        primary_key=True,
    )

    # nombre específico del insumo (ej. "Cascara de naranja dulce")
    nombre = db.Column(db.String(100), nullable=False)

    # tipo de insumo OTRO
    tipo = db.Column(
        db.Enum("SALES", "ADJUNTOS", "EXTRACTOS", "FRUTAS", name="tipo_otro_mtp"),
        nullable=False,
    )

    materia_prima = db.relationship(
        "MateriaPrima", back_populates="otros_detalle", uselist=False
    )

    def __repr__(self):
        return f"<OtrosMtpDetalle MP:{self.id_materia_prima} {self.tipo} {self.nombre}>"


class LoteMateriaPrima(db.Model):
    __tablename__ = "lote_materia_prima"

    id = db.Column("id_lote", db.Integer, primary_key=True)
    id_materia_prima = db.Column(
        db.Integer,
        db.ForeignKey("materia_prima.id_materia_prima", ondelete="RESTRICT"),
        nullable=False,
    )
    codigo_lote = db.Column(db.String(100), nullable=False)
    fecha_compra = db.Column(db.Date)
    proveedor = db.Column(db.String(150))
    cantidad_inicial = db.Column(db.Numeric(10, 3), nullable=False)
    cantidad_disponible = db.Column(db.Numeric(10, 3), nullable=False)
    costo_unitario = db.Column(db.Numeric(10, 2))
    fecha_vencimiento = db.Column(db.Date)
    notas = db.Column(db.Text)
    generacion_actual = db.Column(db.SmallInteger, default=0)

    materia_prima = db.relationship(
        "MateriaPrima", back_populates="lotes"
    )

    def __repr__(self):
        return f"<LoteMateriaPrima {self.id} MP:{self.id_materia_prima} {self.codigo_lote}>"

# ============================
#   RECETAS Y BACHES
# ============================

class Receta(db.Model):
    __tablename__ = "receta"

    id = db.Column("id_receta", db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    estilo = db.Column(db.String(100))
    descripcion = db.Column(db.Text)
    volumen_estandar_litros = db.Column(db.Numeric(10, 2))

    baches = db.relationship("Bache", back_populates="receta", lazy="dynamic")

    def __repr__(self):
        return f"<Receta {self.id} {self.nombre}>"


class Bache(db.Model):
    __tablename__ = "bache"

    id = db.Column("id_bache", db.Integer, primary_key=True)
    codigo_bache = db.Column(db.String(100), nullable=False, unique=True)
    nombre_cerveza = db.Column(db.String(100), nullable=False)

    id_receta = db.Column(
        db.Integer,
        db.ForeignKey("receta.id_receta", ondelete="SET NULL"),
        nullable=True,
    )

    fecha_coccion = db.Column(db.Date, nullable=False)
    volumen_objetivo_litros = db.Column(db.Numeric(10, 2))
    volumen_final_litros = db.Column(db.Numeric(10, 2))
    densidad_inicial = db.Column(db.Numeric(6, 3))
    ph_macerado = db.Column(db.Numeric(4, 2))
    ph_fin_hervido = db.Column(db.Numeric(4, 2))
    temp_maceracion = db.Column(db.Numeric(5, 2))
    temp_mashoff = db.Column(db.Numeric(5, 2))

    estado = db.Column(
        db.Enum(
            "PLANIFICADO",
            "EN_CURSO",
            "FERMENTANDO",
            "MADURANDO",
            "LISTO",
            "COMPLETADO",
            "DESCARTADO",
            name="estado_bache",
        ),
        default="PLANIFICADO",
    )

    notas = db.Column(db.Text)

    receta = db.relationship("Receta", back_populates="baches")

    materias_primas = db.relationship(
        "BacheMateriaPrima", back_populates="bache", lazy="dynamic"
    )

    mediciones = db.relationship(
        "MedicionBache",
        back_populates="bache",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )

    usos_levadura = db.relationship(
        "BacheLevaduraUso",
        back_populates="bache",
        cascade="all, delete-orphan",
        lazy="select",
        foreign_keys="BacheLevaduraUso.id_bache",
    )

    movimientos_barril = db.relationship(
        "MovimientoBarril", back_populates="bache", lazy="dynamic"
    )

    sesiones_cata = db.relationship(
        'SesionCata',
        backref='bache',
        lazy=True,
        cascade='all, delete-orphan'
    )

    def __repr__(self):
        return f"<Bache {self.id} {self.codigo_bache}>"

class BacheMateriaPrima(db.Model):
    __tablename__ = "bache_materia_prima"

    id = db.Column("id_bache_materia", db.Integer, primary_key=True)

    id_bache = db.Column(
        db.Integer,
        db.ForeignKey("bache.id_bache", ondelete="CASCADE"),
        nullable=False,
    )
    id_lote = db.Column(
        db.Integer,
        db.ForeignKey("lote_materia_prima.id_lote", ondelete="RESTRICT"),
        nullable=False,
    )

    cantidad_usada = db.Column(db.Numeric(10, 3), nullable=False)
    unidad = db.Column(
        db.Enum("KG", "G", "L", "ML", "UNIDAD", name="unidad_bmp"),
        nullable=False,
    )

    # Etapa de proceso: maceración, hervor, whirlpool, fermentación, etc.
    etapa_proceso = db.Column(
        db.Enum(
            "MACERACION",
            "HERVOR",
            "WHIRLPOOL",
            "FERMENTACION",
            "MADURACION",
            "OTRA",
            name="etapa_proceso_bmp",
        ),
        nullable=False,
        default="OTRA",
    )

    # Tipo de aplicación: amargor, sabor, aroma, dry hop, etc.
    tipo_aplicacion = db.Column(
        db.Enum(
            "GENERAL",
            "AMARGOR",
            "SABOR",
            "AROMA",
            "DRY_HOP",
            "NUTRIENTE",
            "OTRA",
            name="tipo_aplicacion_bmp",
        ),
        nullable=False,
        default="GENERAL",
    )

    # Para hervido / whirlpool (minutos desde inicio de hervor)
    tiempo_minutos_desde_inicio_hervor = db.Column(db.Integer)

    # Para fermentación (ej: dry hop a día 3)
    dias_desde_inicio_fermentacion = db.Column(db.Integer)

    notas = db.Column(db.Text)

    bache = db.relationship("Bache", back_populates="materias_primas")
    lote = db.relationship("LoteMateriaPrima")

    def __repr__(self):
        return f"<BacheMateriaPrima {self.id} Bache:{self.id_bache} Lote:{self.id_lote}>"

class MedicionBache(db.Model):
    __tablename__ = "medicion_bache"

    id = db.Column("id_medicion", db.Integer, primary_key=True)

    id_bache = db.Column(
        db.Integer,
        db.ForeignKey("bache.id_bache", ondelete="CASCADE"),
        nullable=False,
    )

    # antes: fecha_hora
    fecha = db.Column(db.DateTime, nullable=False)

    tipo = db.Column(
        db.Enum("PH", "TEMPERATURA", "DENSIDAD", "OTRO", name="tipo_medicion_bache"),
        nullable=False,
    )

    valor = db.Column(db.Numeric(10, 3), nullable=False)

    comentario = db.Column(db.Text)

    bache = db.relationship("Bache", back_populates="mediciones")

    def __repr__(self):
        return f"<Medicion Bache:{self.id_bache} {self.tipo} {self.valor}>"

class BacheLevaduraUso(db.Model):
    __tablename__ = "bache_levadura_uso"

    id = db.Column("id_bache_levadura", db.Integer, primary_key=True)

    id_bache = db.Column(
        db.Integer,
        db.ForeignKey("bache.id_bache", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    id_lote = db.Column(
        db.Integer,
        db.ForeignKey("lote_materia_prima.id_lote", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    tipo_uso = db.Column(
        db.Enum("NUEVA", "REUTILIZADA", name="tipo_uso_levadura"),
        nullable=False,
    )

    # 0 para NUEVA; 1..8 para reutilizada
    generacion = db.Column(db.SmallInteger, nullable=False, default=0)

    fecha_inoculacion = db.Column(db.DateTime, nullable=False)
    comentarios = db.Column(db.Text)

    __table_args__ = (
        db.UniqueConstraint("id_bache", "id_lote", name="uq_bache_lote_levadura"),
    )

    bache = db.relationship("Bache", back_populates="usos_levadura", foreign_keys=[id_bache])
    lote = db.relationship("LoteMateriaPrima")

    def __repr__(self):
        return f"<BacheLevaduraUso {self.id} Bache:{self.id_bache} Lote:{self.id_lote} Gen:{self.generacion}>"

# ============================
#   BARRILES Y CLIENTES
# ============================

class Barril(db.Model):
    __tablename__ = "barril"

    id = db.Column("id_barril", db.Integer, primary_key=True)
    codigo_barril = db.Column(db.String(100), nullable=False, unique=True)
    capacidad_litros = db.Column(db.Numeric(10, 2), nullable=False)
    fecha_ingreso = db.Column(db.Date)
    estado_actual = db.Column(
        db.Enum(
            "LIMPIO",
            "LLENO",
            "ENTREGADO",
            "SUCIO",
            "MANTENIMIENTO",
            "BAJA",
            name="estado_barril",
        ),
        nullable=False,
        default="LIMPIO",
    )
    notas = db.Column(db.Text)

    movimientos = db.relationship(
        "MovimientoBarril",
        back_populates="barril",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )


class Cliente(db.Model):
    __tablename__ = "cliente"

    id = db.Column("id_cliente", db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False)
    tipo = db.Column(
        db.Enum(
            "BAR",
            "RESTAURANTE",
            "EVENTO",
            "TAPROOM_INTERNO",
            "OTRO",
            name="tipo_cliente",
        ),
        default="OTRO",
    )
    contacto = db.Column(db.String(150))
    telefono = db.Column(db.String(50))
    direccion = db.Column(db.String(200))
    activo = db.Column(db.Boolean, default=True)

    movimientos = db.relationship(
        "MovimientoBarril", back_populates="cliente", lazy="dynamic"
    )

    def __repr__(self):
        return f"<Cliente {self.id} {self.nombre}>"

class MovimientoBarril(db.Model):
    __tablename__ = "movimiento_barril"

    id = db.Column("id_movimiento", db.Integer, primary_key=True)

    id_barril = db.Column(
        db.Integer,
        db.ForeignKey("barril.id_barril", ondelete="CASCADE"),
        nullable=False,
    )

    fecha_hora = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    tipo_movimiento = db.Column(
        db.Enum(
            "ALTA",
            "LLENO",
            "ENTREGADO",
            "DEVUELTO",
            "LATAS",
            "LAVADO",
            "BAJA",
            name="tipo_movimiento_barril",
        ),
        nullable=False,
    )

    id_bache = db.Column(
        db.Integer,
        db.ForeignKey("bache.id_bache", ondelete="SET NULL"),
        nullable=True,
    )

    id_cliente = db.Column(
        db.Integer,
        db.ForeignKey("cliente.id_cliente", ondelete="SET NULL"),
        nullable=True,
    )

    id_usuario = db.Column(
        db.Integer,
        db.ForeignKey("usuario.id_usuario", ondelete="SET NULL"),
        nullable=True,
    )

    volumen_litros = db.Column(db.Numeric(10, 2))
    comentario = db.Column(db.Text)

    barril = db.relationship("Barril", back_populates="movimientos")
    bache = db.relationship("Bache")
    cliente = db.relationship("Cliente")
    usuario = db.relationship("Usuario")

class SesionCata(db.Model):
    __tablename__ = 'sesion_cata'

    id_sesion_cata = db.Column(db.Integer, primary_key=True)
    id_bache = db.Column(db.Integer, db.ForeignKey('bache.id_bache'), nullable=False)

    codigo_publico = db.Column(db.String(100), unique=True, nullable=False)
    titulo = db.Column(db.String(200), nullable=True)
    descripcion = db.Column(db.Text, nullable=True)

    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    fecha_inicio = db.Column(db.DateTime, nullable=True)
    fecha_fin = db.Column(db.DateTime, nullable=True)

    activa = db.Column(db.Boolean, default=True, nullable=False)
    creada_por = db.Column(db.Integer, nullable=True)
    observaciones = db.Column(db.Text, nullable=True)

    respuestas = db.relationship(
        'RespuestaCata',
        backref='sesion_cata',
        lazy=True,
        cascade='all, delete-orphan'
    )

    def __repr__(self):
        return f"<SesionCata {self.id_sesion_cata} bache={self.id_bache} codigo={self.codigo_publico}>"



class RespuestaCata(db.Model):
    __tablename__ = 'respuesta_cata'

    id_respuesta_cata = db.Column(db.Integer, primary_key=True)
    id_sesion_cata = db.Column(
        db.Integer,
        db.ForeignKey('sesion_cata.id_sesion_cata', ondelete='CASCADE'),
        nullable=False
    )

    fecha_respuesta = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    correo = db.Column(db.String(255), nullable=True)
    sexo = db.Column(db.String(20), nullable=True)
    rango_edad = db.Column(db.String(50), nullable=True)
    nacionalidad = db.Column(db.String(20), nullable=True)

    puntaje_color = db.Column(db.SmallInteger, nullable=False)
    puntaje_carbonatacion_espuma = db.Column(db.SmallInteger, nullable=False)
    puntaje_sabor = db.Column(db.SmallInteger, nullable=False)
    puntaje_aroma = db.Column(db.SmallInteger, nullable=False)
    puntaje_impresion_general = db.Column(db.SmallInteger, nullable=False)

    color_valor = db.Column(db.SmallInteger, nullable=False)
    color_categoria = db.Column(db.String(20), nullable=True)

    carbonatacion_nivel = db.Column(db.String(10), nullable=False)
    espuma_nivel = db.Column(db.String(10), nullable=False)
    cuerpo_nivel = db.Column(db.String(10), nullable=True)

    impresion_general_texto = db.Column(db.Text, nullable=True)

    ip_origen = db.Column(db.String(100), nullable=True)
    user_agent = db.Column(db.Text, nullable=True)

    sabores = db.relationship(
        'RespuestaCataSabor',
        backref='respuesta_cata',
        lazy=True,
        cascade='all, delete-orphan'
    )

    aromas = db.relationship(
        'RespuestaCataAroma',
        backref='respuesta_cata',
        lazy=True,
        cascade='all, delete-orphan'
    )

    def __repr__(self):
        return f"<RespuestaCata {self.id_respuesta_cata} sesion={self.id_sesion_cata}>"



class RespuestaCataSabor(db.Model):
    __tablename__ = 'respuesta_cata_sabor'

    id_respuesta_cata_sabor = db.Column(db.Integer, primary_key=True)
    id_respuesta_cata = db.Column(
        db.Integer,
        db.ForeignKey('respuesta_cata.id_respuesta_cata', ondelete='CASCADE'),
        nullable=False
    )
    sabor = db.Column(db.String(50), nullable=False)

    def __repr__(self):
        return f"<RespuestaCataSabor respuesta={self.id_respuesta_cata} sabor={self.sabor}>"



class RespuestaCataAroma(db.Model):
    __tablename__ = 'respuesta_cata_aroma'

    id_respuesta_cata_aroma = db.Column(db.Integer, primary_key=True)
    id_respuesta_cata = db.Column(
        db.Integer,
        db.ForeignKey('respuesta_cata.id_respuesta_cata', ondelete='CASCADE'),
        nullable=False
    )
    aroma = db.Column(db.String(50), nullable=False)

    def __repr__(self):
        return f"<RespuestaCataAroma respuesta={self.id_respuesta_cata} aroma={self.aroma}>"