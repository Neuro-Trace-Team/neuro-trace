import os

# Configuration is validated on application import.  Real service values are
# always provided by Compose; these local values only make isolated API tests
# independent from developer infrastructure.
os.environ.setdefault("DB_AUTH_URL", "postgresql://user:password@localhost:5432/auth_db")
os.environ.setdefault("DB_MEDICAL_URL", "postgresql://user:password@localhost:5433/medical_db")
os.environ.setdefault("DB_AUDIT_URL", "postgresql://user:password@localhost:5434/audit_db")
os.environ.setdefault("RUSTFS_ENDPOINT", "http://localhost:9000")
os.environ.setdefault("RUSTFS_ACCESS_KEY", "test-access-key")
os.environ.setdefault("RUSTFS_SECRET_KEY", "test-secret-key")
os.environ.setdefault("PREPROCESSING_URL", "http://localhost:8001")
os.environ.setdefault("JWT_SECRET", "test-secret-that-is-long-enough-for-validation")
