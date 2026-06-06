CREATE VIEW protein_data.batch_input AS 
SELECT ROW_NUMBER() OVER (ORDER BY seq) sequence_id, seq
FROM protein_data.training_seq