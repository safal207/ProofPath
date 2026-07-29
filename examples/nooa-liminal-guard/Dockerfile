FROM python:3.12-slim

RUN useradd --create-home --uid 10001 guard
WORKDIR /app
COPY nooa_liminal_guard.py run_demo.py policy.json ./
COPY fixtures ./fixtures
RUN mkdir -p /evidence /state && chown -R guard:guard /app /evidence /state
USER guard

ENTRYPOINT ["python3", "run_demo.py"]
CMD ["--output", "/evidence", "--state", "/state"]
