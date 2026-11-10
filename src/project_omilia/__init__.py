def main() -> None:
    """Запуск сервера приложения Project Omilia."""
    import uvicorn
    uvicorn.run("project_omilia.serv:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
