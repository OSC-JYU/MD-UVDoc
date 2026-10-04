# UVDoc

Flattens **photographed document pages**. Photos taken with a phone or camera are rarely straight:
the page is seen at an angle, and book pages curve towards the spine. UVDoc estimates how the page
is bent and redraws it as a flat, straight page, as if it had been scanned.

It uses [UVDoc](https://github.com/tanguymagne/UVDoc), a neural network that predicts a grid of
points over the page and unwarps the image along it.

## Task

**Dewarp image** takes a PNG or JPEG photo of a page and writes the flattened page as an image of
the same size. PNG stays PNG; other images become JPEG.

## When to use it

- Before OCR (**Tesseract**, **Finnish PaddleOCR**) or line segmentation, on photos of books,
  letters and documents: text recognition assumes straight lines, and curved or slanted lines
  lower its accuracy a lot.
- To make photographed pages easier to read and compare.

It is not needed for flatbed scans, which are already flat; there it changes little, but it can
add slight distortion, so check the result.

## Tips

- One page per photo works best. Split double-page spreads first.
- The whole page should be in the photo, with a little background around it.
- The page is redrawn from the photo, so very small or blurred text does not become sharper.

## About UVDoc

*UVDoc: Neural Grid-based Document Unwarping* by Floor Verhoeven, Tanguy Magne and Olga
Sorkine-Hornung (SIGGRAPH Asia 2023); [code and model](https://github.com/tanguymagne/UVDoc)
under the MIT licence.
