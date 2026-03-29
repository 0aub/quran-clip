.PHONY: build run list-surahs list-reciters test lint clean

build:
	docker build -t quran-clip .

run:
	docker run --rm -it -v ./output:/app/output quran-clip $(ARGS)

list-surahs:
	docker run --rm -it quran-clip list-surahs

list-reciters:
	docker run --rm -it quran-clip list-reciters

test:
	docker run --rm --entrypoint pytest quran-clip -v

lint:
	docker run --rm --entrypoint ruff quran-clip check src/ tests/

clean:
	rm -rf output/*.mp3 output/*.opus output/*.ogg output/*.wav
