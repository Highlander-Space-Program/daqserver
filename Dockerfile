FROM ghcr.io/astral-sh/uv:debian

WORKDIR /app

# ---- Cache-friendly dependency install ----
# Copy only dependency files first
COPY pyproject.toml uv.lock ./

# Install dependencies (no project code yet)
RUN uv sync --frozen --no-install-project

# ---- App layer ----
# Now copy the rest of the app
COPY . .

# Install project itself (fast, since deps are cached)
RUN uv sync --frozen


CMD ["uv", "run", "server"]
