name := dialatedtree

.PHONY: image
image: Containerfile
	podman build -t $(name) .

.PHONY: grocycli
grocycli: grocycli.Containerfile
	podman build -f grocycli.Containerfile -t grocycli .

.PHONY: serve
serve: index.html
	python3 -m http.server 8080
