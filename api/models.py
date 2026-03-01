from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, LargeBinary, String
from sqlalchemy.orm import relationship

try:
    from .database import Base
except ImportError as exc:  # pragma: no cover
    if "attempted relative import with no known parent package" not in str(exc):
        raise
    from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    github_id = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    avatar_url = Column(String, default="", nullable=False)

    problems = relationship("Problem", back_populates="owner", cascade="all, delete-orphan")
    solvers = relationship("Solver", back_populates="owner", cascade="all, delete-orphan")


class Problem(Base):
    __tablename__ = "problems"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    version = Column(String, nullable=False)
    description = Column(String, nullable=False)
    category = Column(String, nullable=True)
    download_count = Column(Integer, default=0, nullable=False)
    rating = Column(Float, default=0.0, nullable=False)
    rating_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    owner = relationship("User", back_populates="problems")
    versions = relationship(
        "ProblemVersion",
        back_populates="problem",
        cascade="all, delete-orphan",
        order_by="ProblemVersion.created_at.desc()",
    )


class Solver(Base):
    __tablename__ = "solvers"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    version = Column(String, nullable=False)
    description = Column(String, nullable=False)
    category = Column(String, nullable=True)
    download_count = Column(Integer, default=0, nullable=False)
    rating = Column(Float, default=0.0, nullable=False)
    rating_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    owner = relationship("User", back_populates="solvers")
    versions = relationship(
        "SolverVersion",
        back_populates="solver",
        cascade="all, delete-orphan",
        order_by="SolverVersion.created_at.desc()",
    )


class ProblemVersion(Base):
    __tablename__ = "problem_versions"

    id = Column(Integer, primary_key=True, index=True)
    problem_id = Column(Integer, ForeignKey("problems.id"), nullable=False)
    version = Column(String, nullable=False)
    description = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    problem = relationship("Problem", back_populates="versions")


class SolverVersion(Base):
    __tablename__ = "solver_versions"

    id = Column(Integer, primary_key=True, index=True)
    solver_id = Column(Integer, ForeignKey("solvers.id"), nullable=False)
    version = Column(String, nullable=False)
    description = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    solver = relationship("Solver", back_populates="versions")


class ArchiveBlob(Base):
    __tablename__ = "archive_blobs"

    key = Column(String, primary_key=True, index=True)
    data = Column(LargeBinary, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
