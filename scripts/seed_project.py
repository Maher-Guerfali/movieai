import requests

API = "http://localhost:8000/api"


def main() -> None:
    project = requests.post(
        f"{API}/projects",
        json={"name": "Lili Marleen - Damascus", "style": "Waltz with Bashir"},
        timeout=10,
    ).json()
    requests.post(f"{API}/projects/{project['id']}/seed", json={}, timeout=10)
    requests.post(f"{API}/projects/{project['id']}/start", timeout=20)
    print(f"Seeded project {project['id']}")


if __name__ == "__main__":
    main()
