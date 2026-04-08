from app import app


if __name__ == "__main__":
    import uvicorn

    print("Judge service starting at http://localhost:19000")
    print("Supported assignment types: normal, process, file, memory")
    uvicorn.run(app, host="0.0.0.0", port=8000)
