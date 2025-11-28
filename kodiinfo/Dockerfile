FROM python:3.12-slim
WORKDIR /app
COPY kodi-nowplaying.py parser.py movie_nowplaying.py episode_nowplaying.py music_nowplaying.py favicon.ico play-button.png pause-button.png /app/
RUN pip install flask requests
EXPOSE 5001
CMD ["python", "kodi-nowplaying.py"]
