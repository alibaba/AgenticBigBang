# MOPD training records

`data/manifests/mopd_training_records.csv` contains the upsampled MOPD
training list: 4956 records (1652 per category),
2769 distinct Initial-RL source records, and 2768 distinct tasks.

- `mopd_record_id`: unique identifier for each materialized copy, with prefix `MOPD-`.
- `manifest_position`: one-based row position in the supplied list. This preserves
  the list order; it does not assert the runtime minibatch or shuffled execution order.
- `anon_instance_id`: stable TRN task identifier shared with other manifests.
- `source_record_id`: REC identifier linking to `initial_rl_training_records.csv`.
- `teacher_category`: A/B/C routing category inherited from the source record.
- `upsample_occurrence`: one-based occurrence of that source REC in this list.

The source `record_occurrence` describes duplicate task records in Initial RL;
it is not an upsampling copy number. These two concepts are kept separate.
In particular, the duplicated C task has two source REC identifiers and one TRN
identifier. Neither internal task IDs nor source paths are exported.
