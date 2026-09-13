from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship
from app.core.database import Base


class Language(Base):
    __tablename__ = "languages"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    code = Column(String(10), unique=True, index=True, nullable=False)
    name = Column(String(50), nullable=False)
    native_name = Column(String(50), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    interviews = relationship("Interview", back_populates="language")
    translations = relationship("ClinicalOntologyFieldTranslation", back_populates="language")


class ClinicalOntologyFieldTranslation(Base):
    __tablename__ = "clinical_ontology_field_translations"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    field_key = Column(
        String(50),
        ForeignKey("clinical_ontology_fields.field_key", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    language_code = Column(
        String(10),
        ForeignKey("languages.code", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    display_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("field_key", "language_code", name="uq_field_language_translation"),
    )

    ontology_field = relationship("ClinicalOntologyField", back_populates="translations")
    language = relationship("Language", back_populates="translations")
