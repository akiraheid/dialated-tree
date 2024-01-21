name := dialatedtree

.PHONY: image
image: Containerfile
	podman build -t $(name) .

.PHONY: serve
serve: index.html
	python3 -m http.server 8080
