-- Checking for class imbalance in the 8 class structure labels

SELECT sst8_char AS structure_class, COUNT(*) AS cnt,
  ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct
FROM protein_data.training_seq,
UNNEST(SPLIT(sst8, '')) AS sst8_char
GROUP BY sst8_char
ORDER BY cnt DESC;

