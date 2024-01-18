name := dialatedtree

.PHONY: image
image: Containerfile
	podman build -t $(name) .
