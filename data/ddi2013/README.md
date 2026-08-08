---
dataset_info:
  features:
  - name: id
    dtype: string
  - name: conversations
    list:
    - name: from
      dtype: string
    - name: value
      dtype: string
  - name: text
    dtype: string
  splits:
  - name: train
    num_bytes: 40950848
    num_examples: 18779
  download_size: 7546175
  dataset_size: 40950848
configs:
- config_name: default
  data_files:
  - split: train
    path: data/train-*
---
