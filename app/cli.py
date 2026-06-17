from app.core.config import get_settings


def main() -> None:
    settings = get_settings()
    print(f"AI Article Editor ({settings.app_env})")


if __name__ == "__main__":
    main()
