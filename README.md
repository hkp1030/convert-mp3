# convert-mp3

동영상 파일을 MP3로 빠르게 변환하는 CLI 도구. FFmpeg를 활용하며 모든 CPU 코어를 사용해 병렬 인코딩합니다.

## 동작 방식

1. 입력 파일의 전체 길이를 측정 (`ffprobe`)
2. 영상을 CPU 코어 수만큼 구간으로 분할
3. 각 구간을 병렬로 MP3 인코딩 (`libmp3lame`)
4. 완성된 세그먼트를 순서대로 이어 붙여 최종 MP3 생성

짧은 파일(10초 미만)이나 단일 워커 실행 시에는 분할 없이 바로 변환합니다.

## 요구 사항

- Python 3.11+
- [FFmpeg](https://ffmpeg.org/) (`ffmpeg`, `ffprobe`가 PATH에 있어야 함)

## 설치

```bash
uv sync
```

설치 후 `tomp3` 명령어를 사용할 수 있습니다.

## 사용법

```bash
# 기본 사용
tomp3 video.mp4

# 여러 파일 한 번에 변환
tomp3 video1.mp4 video2.mkv video3.avi

# VBR 품질 지정 (0=최고, 9=최저, 기본값: 2)
tomp3 -q 0 video.mp4

# 병렬 워커 수 지정 (기본값: 전체 CPU 코어)
tomp3 -j 4 video.mp4
```

## 옵션

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `-q`, `--quality` | MP3 VBR 품질 (0=최고, 9=최저) | `2` |
| `-j`, `--jobs` | 병렬 워커 수 | 전체 CPU 코어 수 |

## 출력

변환된 MP3 파일은 원본과 같은 디렉터리에 동일한 이름으로 저장됩니다.

```
video.mp4 → video.mp3
```
