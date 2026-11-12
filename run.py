from src.nepal_firewatch.pipeline import run_pipeline

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Nepal FireWatch pipeline")
    parser.add_argument("--demo", action="store_true", help="Use bundled demo FIRMS detections and demo boundaries")
    args = parser.parse_args()

    result = run_pipeline(demo=args.demo)
    print(
        "Nepal FireWatch complete | "
        f"fetched={result['fetched']} | "
        f"new_detections={result['new_detections']} | "
        f"new_events={result['new_events']}"
    )
