FROM python:3.12-slim

WORKDIR /app
COPY . .
RUN pip install --no-cache-dir ".[ui]" \
    && useradd --create-home --uid 1000 app

USER app
EXPOSE 8000

# Only answer requests for localhost (protects against DNS rebinding).
# On a server, set PROMPT2IMAGE_ALLOWED_HOSTS to its host name, or * for any.
ENV PROMPT2IMAGE_ALLOWED_HOSTS=localhost,127.0.0.1,::1

# The web page: create, edit and describe images in the browser.
# Settings come from PROMPT2IMAGE_* environment variables, or from the fields on the page.
CMD ["prompt2image", "serve", "--host", "0.0.0.0", "--port", "8000"]
