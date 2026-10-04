CONTAINER_RUNTIME ?= podman
VERSION := 0.2
REPOSITORY := localhost/messydesk
IMAGE := md-uvdoc
LOCAL_IMAGE := $(REPOSITORY)/$(IMAGE):$(VERSION)

build:
	$(CONTAINER_RUNTIME) build -t $(LOCAL_IMAGE) .

start:
	$(CONTAINER_RUNTIME) run -d --name $(IMAGE) -p 9006:9006 --restart unless-stopped $(LOCAL_IMAGE)

stop:
	-$(CONTAINER_RUNTIME) stop $(IMAGE)
	-$(CONTAINER_RUNTIME) rm $(IMAGE)

restart: stop start

bash:
	$(CONTAINER_RUNTIME) exec -it $(IMAGE) bash

# The tests run in the service image (tests/ and test/ are not copied into it).
test: build
	$(CONTAINER_RUNTIME) run --rm -e HOME=/tmp -e PYTHONUSERBASE=/tmp/pyuser -v $(CURDIR)/tests:/app/tests:ro,Z -v $(CURDIR)/test:/app/test:ro,Z -v $(CURDIR)/model:/app/model:ro,Z $(LOCAL_IMAGE) \
		sh -c "pip install -q --user pytest httpx pillow && python -m pytest -q -p no:cacheprovider tests"
