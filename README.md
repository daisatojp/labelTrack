# labelTrack

In visual tracking dataset, a sequence of images has one object for each image, in contrast to object detection dataset that has multiple objects in each image. This annotation tool is suited for that.

## Quick Start

```bash
git clone https://github.com/daisatojp/labelTrack.git
cd labelTrack
pip install PyQt6==6.6.1 PyQt6-Qt6==6.6.3
python labelTrack.py
```

* Click `Open Label File` in toolbar to select label file to be saved.
* Click `Open Image Dir` in toolbar to open a folder containing a sequence of images.
* Click `Create Object` in toolbar and make box by a mouse dragging in each image.
* Click `Save` in toolbar to save label file.

## Label Format

```text
<x coord of top-left>,<y coord of top-left>,<width>,<height>
<x coord of top-left>,<y coord of top-left>,<width>,<height>
<x coord of top-left>,<y coord of top-left>,<width>,<height>
...
...
...
```

More concretely, see [sample/label.txt](https://github.com/daisatojp/labelTrack/blob/main/sample/label.txt).

## Useful Shortcuts

| Key | Action |
| --- | --------------- |
| `d` | open next image |
| `a` | open previous image |
| `w` | create bounding box |
| `c` | remove bounding box |
| `r` | copy bounding box from previous image |
| `t` | open next image and copy bounding box from previous image |
| `v` | open next image and remove bounding box |

## Acknowledgment

* [labelimg](https://github.com/tzutalin/labelImg) as a reference.
