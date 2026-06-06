import torch
import torch.nn as nn


class lstm_model(nn.Module):
    """
    Bidirectional LSTM model for protein secondary structure prediction.
    
    This model processes amino acid sequences through an embedding layer, followed by
    a bidirectional LSTM, layer normalization, dropout, and a final linear layer
    to predict secondary structure labels for each amino acid position.
    
    Attributes:
        pad_id (int): Padding token index
        embed (nn.Embedding): Embedding layer for amino acid sequences
        lstm (nn.LSTM): Bidirectional LSTM layer
        norm (nn.LayerNorm): Layer normalization
        dropout (nn.Dropout): Dropout layer for regularization
        final_layer (nn.Linear): Final linear layer for classification
    """
    
    def __init__(self, vocab_size, num_tags, pad_id, hidden=64, embed_dim=64, bidir=False):
        """
        Initialize the LSTM model.
        
        Args:
            vocab_size (int): Vocabulary dictionary for amino acids
            num_tags (int): Number of output classes (secondary structure types)
            pad_id (int): Padding token index
            hidden (int, optional): Hidden dimension of LSTM. Defaults to 64.
            embed_dim (int, optional): Embedding dimension. Defaults to 64.
            bidir (bool, optional): Whether to use bidirectional LSTM. Defaults to False.
        """
        super().__init__()
        
        self.pad_id = pad_id
        self.embed = nn.Embedding(num_embeddings=vocab_size, embedding_dim=embed_dim, padding_idx=pad_id)
        
        # Two-layer LSTM with bidirectional processing
        # Bidirectional LSTM processes the sequence forwards and backwards and concatenates the outputs
        self.lstm = nn.LSTM(input_size=embed_dim, hidden_size=hidden, num_layers=2, batch_first=True, bidirectional=bidir) 

        # Output dimension doubles if bidirectional is True
        out_dim = hidden * (2 if bidir else 1)
        self.norm = nn.LayerNorm(out_dim)
        self.dropout = nn.Dropout(p=0.2)  # Optional, but can help with stability

        # Final linear layer maps to output classes
        self.final_layer = nn.Linear(out_dim, num_tags)

    def forward(self, x):
        """
        Forward pass through the model.
        
        Args:
            x (torch.Tensor): Input tensor of shape [batch_size, seq_len]
            
        Returns:
            torch.Tensor: Output logits of shape [batch_size, seq_len, num_classes]
        """
        # Input: [B, T] where B = batch size, T = sequence length (tokens)
        e = self.embed(x)  # Embedding layer: [B, T, E] where E = embedding dimension
        h, _ = self.lstm(e)  # LSTM layer: [B, T, H * (1 | 2)] where H = hidden dimension
        h = self.norm(h)  # Layer normalization across dimensions
        h = self.dropout(h)
        logits = self.final_layer(h)  # Final layer: [B, T, C] where C = number of classes

        return logits