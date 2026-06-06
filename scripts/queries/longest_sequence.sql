-- Finding the longest sequence (for inference)
-- 
SELECT LENGTH(seq) AS seq_length, seq, sst3, sst8
FROM protein_data.training_seq
ORDER BY seq_length
LIMIT 10;
