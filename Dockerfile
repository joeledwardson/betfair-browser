FROM python:3.10.6
WORKDIR /app
# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -
# Add poetry to Path
ENV PATH="/root/.local/bin:$PATH"
# upgrade pip to latest version
RUN pip install --upgrade pip
# Copy only the "pyproject.toml" and "poetry.lock" files to the container
COPY pyproject.toml poetry.lock ./
# Install dependencies using Poetry
RUN poetry install
# Ensure setuptools is installed
RUN poetry run pip install setuptools
# Copy the rest of the application code into the container
COPY . ./
# Build CSS
RUN poetry run python ./makecss.py
# run application
CMD ["poetry", "run", "python", "browser_local.py"]