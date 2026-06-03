import os
import sys

import requests

API = "http://localhost:8000/api"

DEFAULT_IDEA = (
    "A retired lighthouse keeper on a remote coast discovers a stranded sea "
    "creature and must protect it from an approaching storm and the fearful townsfolk."
)


def main() -> None:
    idea = " ".join(sys.argv[1:]) or os.environ.get("MOVIE_IDEA", DEFAULT_IDEA)
    style = os.environ.get("MOVIE_STYLE", "Studio Ghibli watercolor, warm cinematic light")

    project = requests.post(
        f"{API}/projects",
        json={"name": "Untitled Movie", "style": style},
        timeout=10,
    ).json()
    # The Writer generates the story from the idea (requires a real API key
    # unless USE_MOCK_AI=true).
    requests.post(
        f"{API}/projects/{project['id']}/seed",
        json={"instruction": idea},
        timeout=120,
    )
    requests.post(f"{API}/projects/{project['id']}/start", timeout=30)
    print(f"Seeded project {project['id']} from idea: {idea[:60]}…")


if __name__ == "__main__":
    main()
