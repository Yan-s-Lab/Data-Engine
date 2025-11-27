from libs.core_db.session import engine, Base
from libs.core_db import models  # noqa: F401  触发表加载


def main():
    print("Creating tables...")
    Base.metadata.create_all(bind=engine)
    print("Done!")


if __name__ == "__main__":
    main()
