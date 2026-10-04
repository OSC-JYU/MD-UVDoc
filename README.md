# MD-UVDoc

[UVDoc](https://github.com/tanguymagne/UVDoc) for MessyDesk: flattens photographed document
pages (perspective and page curl). The user help is [help/index.md](help/index.md) (served at
`/help`); the task is in [service.json](service.json) (served at `/config`).

| Task | Input | Output |
|---|---|---|
| `dewarp` | PNG or JPEG image | `<image label>.png` for PNG input, `<image label>.jpg` otherwise, type `image`, same size |

The model (`model/best_model.pkl`) is in the repository and the image. It loads on the first job
and runs on CPU (CUDA when available). The rest of this repository (training, benchmarks, demo)
is UVDoc's own code and is not used by the service.

## Running

```bash
make build
make start
```

The service listens on port 9006. `make` uses podman; `CONTAINER_RUNTIME=docker make build` for
Docker.

### Example call (HTTP mode)

	curl -F "message=@test/dewarp.json;type=application/json" -F "content=@test/page.png" \
	  http://localhost:9006/process

## Storage modes

- **Disk mode** when `MD_PATH` points at the MessyDesk root (the directory that contains `data/`):
  the image is read from `message.file.path`, the result is written to `MD_PATH/data/<db>/tmp/`,
  and `/config` reports the `elg_fs` adapter.
- **HTTP mode** otherwise, or with `STORAGE_MODE=http`: the image is the `content` upload, the
  result is served once from `/files/<name>`, and `/config` reports `elg`.

`/config` serves service.json with the adapter of the mode; `SERVICE_ID`, `SERVICE_NAME`,
`SERVICE_ADAPTER` and `SERVICE_LOCAL_URL` override its fields (`md_service.py`).

## Tests

```bash
make test
```

Runs `tests/test_api.py` in the service image with the real model: a page photographed at an
angle is flattened (disk mode), PNG stays PNG (HTTP mode), bad input, and `/config`, `/help` and
`/health`.

---

This is a MessyDesk wrapper for UVDoc

[https://github.com/tanguymagne/UVDoc](https://github.com/tanguymagne/UVDoc)



