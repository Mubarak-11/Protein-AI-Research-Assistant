SELECT aa, COUNT(*) AS cnt
FROM protein_data.training_seq,
UNNEST(SPLIT(seq, '')) AS aa
GROUP BY aa
ORDER BY cnt DESC;
