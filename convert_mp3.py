import argparse
import json
import multiprocessing
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


def validate_media_file(filepath: str) -> str | None:
    """파일이 오디오 스트림을 포함한 유효한 미디어 파일인지 검증한다.

    Returns:
        None이면 유효, 문자열이면 에러 메시지.
    """
    # fmt: off
    result = subprocess.run(
        [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_streams',
            '-select_streams', 'a',
            filepath,
        ],
        capture_output=True, text=True,
    )
    # fmt: on
    if result.returncode != 0:
        return 'not a valid media file'

    try:
        streams = json.loads(result.stdout).get('streams', [])
    except (json.JSONDecodeError, KeyError):
        return 'unable to read media info'

    if not streams:
        return 'no audio stream found'

    return None


def get_duration(filepath: str) -> float:
    # fmt: off
    result = subprocess.run(
        [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format', filepath,
        ],
        capture_output=True, text=True, check=True,
    )
    # fmt: on
    return float(json.loads(result.stdout)['format']['duration'])


def encode_segment(
    input_file: str,
    output_file: str,
    start: float,
    duration: float,
    quality: int,
) -> str:
    # fmt: off
    subprocess.run(
        [
            'ffmpeg', '-y',
            '-hide_banner',
            '-loglevel', 'error',
            '-ss', f'{start:.3f}',
            '-t', f'{duration:.3f}',
            '-i', input_file,
            '-vn',
            '-codec:a', 'libmp3lame',
            '-q:a', str(quality),
            output_file,
        ],
        check=True,
    )
    # fmt: on
    return output_file


def convert_file(
    input_path: str,
    num_workers: int,
    tmpdir: str,
    quality: int,
) -> Path:
    inp = Path(input_path).resolve()
    out = inp.with_suffix('.mp3')
    duration = get_duration(str(inp))

    print(f'  {inp.name} ({duration:.1f}s) -> {num_workers} segments')

    if num_workers <= 1 or duration < 10:
        encode_segment(str(inp), str(out), 0, duration, quality)
        print(f'  OK {out.name}')
        return out

    seg_dur = duration / num_workers
    tasks = []
    for i in range(num_workers):
        seg_out = os.path.join(tmpdir, f'{inp.stem}_seg{i:04d}.mp3')
        tasks.append((str(inp), seg_out, i * seg_dur, seg_dur, quality))

    done = 0
    seg_files: list[str] = [''] * num_workers
    with ThreadPoolExecutor(max_workers=num_workers) as pool:
        futs = {pool.submit(encode_segment, *t): idx for idx, t in enumerate(tasks)}
        for fut in as_completed(futs):
            idx = futs[fut]
            seg_files[idx] = fut.result()
            done += 1
            print(f'  [{done}/{num_workers}] segments done', end='\r', flush=True)

    print()

    concat_list = os.path.join(tmpdir, f'{inp.stem}_concat.txt')
    with open(concat_list, 'w', encoding='utf-8') as f:
        for sf in seg_files:
            f.write(f"file '{sf}'\n")

    # fmt: off
    subprocess.run(
        [
            'ffmpeg', '-y',
            '-hide_banner',
            '-loglevel', 'error',
            '-f', 'concat',
            '-safe', '0',
            '-i', concat_list,
            '-c', 'copy',
            str(out),
        ],
        check=True,
    )
    # fmt: on
    print(f'  OK {out.name}')
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description='Fast video to MP3 converter')
    parser.add_argument('files', nargs='+', help='Video files to convert')
    parser.add_argument(
        '-q',
        '--quality',
        type=int,
        default=2,
        help='MP3 VBR quality (0=best, 9=worst, default: 2)',
    )
    parser.add_argument(
        '-j',
        '--jobs',
        type=int,
        default=multiprocessing.cpu_count(),
        help='Number of parallel workers (default: all CPUs)',
    )
    args = parser.parse_args()

    num_cpus = args.jobs
    files = []
    for f in args.files:
        if not Path(f).is_file():
            print(f"Warning: skipping '{f}' (not found)", file=sys.stderr)
            continue
        error = validate_media_file(f)
        if error:
            print(f"Warning: skipping '{f}' ({error})", file=sys.stderr)
            continue
        files.append(f)

    if not files:
        print('Error: no valid files provided', file=sys.stderr)
        sys.exit(1)

    workers_per_file = max(1, num_cpus // len(files))
    print(f'CPUs: {num_cpus}, files: {len(files)}, workers/file: {workers_per_file}')

    with tempfile.TemporaryDirectory() as tmpdir:
        if len(files) == 1:
            convert_file(files[0], workers_per_file, tmpdir, args.quality)
        else:
            with ThreadPoolExecutor(max_workers=len(files)) as pool:
                futs = [pool.submit(convert_file, f, workers_per_file, tmpdir, args.quality) for f in files]
                for fut in as_completed(futs):
                    fut.result()

    print('Done.')
