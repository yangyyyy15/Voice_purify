"""Make panns-inference 0.1.1 use a project-local label cache on Windows."""
from importlib.metadata import distribution


def main():
    package = distribution("panns-inference")
    path = package.locate_file("panns_inference/config.py")
    source = path.read_text(encoding="utf-8")
    if "PANNS_DATA_DIR" in source:
        print("PANNs local cache support already installed.")
        return
    old = "labels_csv_path = '{}/panns_data/class_labels_indices.csv'.format(str(Path.home()))"
    new = "labels_csv_path = str(Path(os.environ.get('PANNS_DATA_DIR', str(Path.home() / 'panns_data'))) / 'class_labels_indices.csv')"
    if old not in source:
        raise RuntimeError("Unknown PANNs config layout; no files changed.")
    path.write_text(source.replace(old, new, 1), encoding="utf-8")
    print("Enabled PANNS_DATA_DIR in", path)


if __name__ == "__main__":
    main()
