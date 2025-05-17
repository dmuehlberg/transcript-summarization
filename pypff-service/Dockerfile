FROM python:3.10-slim

ENV DEBIAN_FRONTEND=noninteractive

# -------------------------------------------------------------------
# 1) System-Pakete inkl. pffexport-CLI und Python-Bindings
# -------------------------------------------------------------------
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      pff-tools             \
      python3-pypff         \
      swig python3-dev      \
      build-essential       \
      git                    \
      gettext-base           \
 && rm -rf /var/lib/apt/lists/*

# -------------------------------------------------------------------
# 2) Python-Abhängigkeiten
# -------------------------------------------------------------------
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# -------------------------------------------------------------------
# 3) Anwendungscode und Start
# -------------------------------------------------------------------
COPY ./app /app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8100"]