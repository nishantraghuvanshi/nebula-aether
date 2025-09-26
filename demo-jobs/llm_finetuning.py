#!/usr/bin/env python3
"""
LLM Fine-tuning Simulation - Transformer Training Benchmark
Simulates large language model fine-tuning with attention mechanisms
Mac-compatible with CUDA/MPS acceleration
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import math
import time
import argparse

class MultiHeadAttention(nn.Module):
    def __init__(self, d_model, num_heads, device):
        super(MultiHeadAttention, self).__init__()
        self.d_model = d_model
        self.num_heads = num_heads
        self.d_k = d_model // num_heads

        self.W_q = nn.Linear(d_model, d_model, device=device)
        self.W_k = nn.Linear(d_model, d_model, device=device)
        self.W_v = nn.Linear(d_model, d_model, device=device)
        self.W_o = nn.Linear(d_model, d_model, device=device)

        self.dropout = nn.Dropout(0.1)

    def scaled_dot_product_attention(self, Q, K, V, mask=None):
        # Q, K, V: [batch_size, num_heads, seq_len, d_k]
        scores = torch.matmul(Q, K.transpose(-2, -1)) / math.sqrt(self.d_k)

        if mask is not None:
            scores = scores.masked_fill(mask == 0, -1e9)

        attention_weights = F.softmax(scores, dim=-1)
        attention_weights = self.dropout(attention_weights)

        output = torch.matmul(attention_weights, V)
        return output, attention_weights

    def forward(self, query, key, value, mask=None):
        batch_size, seq_len, d_model = query.size()

        # Linear projections
        Q = self.W_q(query).view(batch_size, seq_len, self.num_heads, self.d_k).transpose(1, 2)
        K = self.W_k(key).view(batch_size, seq_len, self.num_heads, self.d_k).transpose(1, 2)
        V = self.W_v(value).view(batch_size, seq_len, self.num_heads, self.d_k).transpose(1, 2)

        # Scaled dot-product attention
        attention_output, attention_weights = self.scaled_dot_product_attention(Q, K, V, mask)

        # Concatenate heads
        attention_output = attention_output.transpose(1, 2).contiguous().view(
            batch_size, seq_len, d_model
        )

        # Final linear projection
        output = self.W_o(attention_output)
        return output, attention_weights

class FeedForward(nn.Module):
    def __init__(self, d_model, d_ff, device):
        super(FeedForward, self).__init__()
        self.linear1 = nn.Linear(d_model, d_ff, device=device)
        self.linear2 = nn.Linear(d_ff, d_model, device=device)
        self.dropout = nn.Dropout(0.1)

    def forward(self, x):
        return self.linear2(self.dropout(F.gelu(self.linear1(x))))

class TransformerBlock(nn.Module):
    def __init__(self, d_model, num_heads, d_ff, device):
        super(TransformerBlock, self).__init__()
        self.attention = MultiHeadAttention(d_model, num_heads, device)
        self.feed_forward = FeedForward(d_model, d_ff, device)
        self.layer_norm1 = nn.LayerNorm(d_model, device=device)
        self.layer_norm2 = nn.LayerNorm(d_model, device=device)
        self.dropout = nn.Dropout(0.1)

    def forward(self, x, mask=None):
        # Self-attention with residual connection
        attn_output, _ = self.attention(x, x, x, mask)
        x = self.layer_norm1(x + self.dropout(attn_output))

        # Feed-forward with residual connection
        ff_output = self.feed_forward(x)
        x = self.layer_norm2(x + self.dropout(ff_output))

        return x

class SimplifiedTransformer(nn.Module):
    def __init__(self, vocab_size, d_model, num_heads, num_layers, d_ff, max_seq_len, device):
        super(SimplifiedTransformer, self).__init__()
        self.d_model = d_model
        self.device = device

        # Embeddings
        self.token_embedding = nn.Embedding(vocab_size, d_model, device=device)
        self.position_embedding = nn.Embedding(max_seq_len, d_model, device=device)

        # Transformer blocks
        self.transformer_blocks = nn.ModuleList([
            TransformerBlock(d_model, num_heads, d_ff, device)
            for _ in range(num_layers)
        ])

        # Output layer
        self.layer_norm = nn.LayerNorm(d_model, device=device)
        self.output_projection = nn.Linear(d_model, vocab_size, device=device)

        # Initialize weights
        self.apply(self._init_weights)

    def _init_weights(self, module):
        if isinstance(module, nn.Linear):
            torch.nn.init.normal_(module.weight, mean=0.0, std=0.02)
            if module.bias is not None:
                torch.nn.init.zeros_(module.bias)
        elif isinstance(module, nn.Embedding):
            torch.nn.init.normal_(module.weight, mean=0.0, std=0.02)

    def forward(self, input_ids, attention_mask=None):
        batch_size, seq_len = input_ids.size()

        # Create position indices
        position_ids = torch.arange(seq_len, dtype=torch.long, device=self.device)
        position_ids = position_ids.unsqueeze(0).expand(batch_size, -1)

        # Embeddings
        token_emb = self.token_embedding(input_ids)
        pos_emb = self.position_embedding(position_ids)
        x = token_emb + pos_emb

        # Scale embeddings
        x = x * math.sqrt(self.d_model)

        # Pass through transformer blocks
        for transformer_block in self.transformer_blocks:
            x = transformer_block(x, attention_mask)

        # Layer normalization and output projection
        x = self.layer_norm(x)
        logits = self.output_projection(x)

        return logits

def generate_synthetic_data(batch_size, seq_len, vocab_size, device):
    """
    Generate synthetic training data for language modeling
    """
    # Create random token sequences
    input_ids = torch.randint(0, vocab_size, (batch_size, seq_len), device=device)

    # Create attention mask (all ones for simplicity) - fixed shape
    attention_mask = torch.ones(batch_size, 1, seq_len, seq_len, device=device)

    # For language modeling, labels are input_ids shifted by one position
    labels = torch.roll(input_ids, -1, dims=1)
    labels[:, -1] = 0  # Set last token to padding

    return input_ids, attention_mask, labels

def calculate_model_parameters(model):
    """
    Calculate total number of parameters in the model
    """
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    return total_params, trainable_params

def main():
    parser = argparse.ArgumentParser(description='LLM Fine-tuning Simulation')
    parser.add_argument('--model-size', type=str, default='small',
                       help='Model size (tiny, small, medium, large)')
    parser.add_argument('--batch-size', type=int, default=4, help='Batch size')
    parser.add_argument('--seq-length', type=int, default=512, help='Sequence length')
    parser.add_argument('--training-steps', type=int, default=1000, help='Number of training steps')
    parser.add_argument('--learning-rate', type=float, default=1e-4, help='Learning rate')
    parser.add_argument('--device', type=str, default='auto', help='Device to use')
    parser.add_argument('--vocab-size', type=int, default=32000, help='Vocabulary size')
    args = parser.parse_args()

    print(f"🤖 Starting LLM Fine-tuning Simulation")
    print(f"   Model size: {args.model_size}")
    print(f"   Batch size: {args.batch_size}")
    print(f"   Sequence length: {args.seq_length}")
    print(f"   Training steps: {args.training_steps}")
    print(f"   Learning rate: {args.learning_rate}")
    print(f"   Vocabulary size: {args.vocab_size}")

    # Model configuration based on size
    model_configs = {
        'tiny': {'d_model': 256, 'num_heads': 4, 'num_layers': 4, 'd_ff': 1024},
        'small': {'d_model': 512, 'num_heads': 8, 'num_layers': 6, 'd_ff': 2048},
        'medium': {'d_model': 768, 'num_heads': 12, 'num_layers': 12, 'd_ff': 3072},
        'large': {'d_model': 1024, 'num_heads': 16, 'num_layers': 24, 'd_ff': 4096},
    }

    if args.model_size not in model_configs:
        print(f"❌ Unsupported model size: {args.model_size}")
        return 1

    config = model_configs[args.model_size]
    print(f"   Model config: {config}")

    # Device selection
    if args.device == 'auto':
        if torch.cuda.is_available():
            device = torch.device('cuda')
            print(f"📱 Using CUDA GPU: {torch.cuda.get_device_name(0)}")
        elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            device = torch.device('mps')
            print("🍎 Using Apple Silicon GPU (MPS)")
        else:
            device = torch.device('cpu')
            print("💻 Using CPU (multi-threaded)")
            torch.set_num_threads(4)
    else:
        device = torch.device(args.device)
        print(f"📱 Using specified device: {device}")

    try:
        # Create model
        print(f"🏗️ Building transformer model...")
        model = SimplifiedTransformer(
            vocab_size=args.vocab_size,
            d_model=config['d_model'],
            num_heads=config['num_heads'],
            num_layers=config['num_layers'],
            d_ff=config['d_ff'],
            max_seq_len=args.seq_length,
            device=device
        )

        # Calculate model size
        total_params, trainable_params = calculate_model_parameters(model)
        model_size_mb = total_params * 4 / (1024 * 1024)  # Assuming float32

        print(f"📊 Model statistics:")
        print(f"   Total parameters: {total_params:,}")
        print(f"   Trainable parameters: {trainable_params:,}")
        print(f"   Model size: {model_size_mb:.1f} MB")

        # Memory estimation
        batch_memory = args.batch_size * args.seq_length * config['d_model'] * 4 / (1024 * 1024)
        estimated_memory = model_size_mb + batch_memory * 3  # Model + activations + gradients
        print(f"💾 Estimated memory usage: {estimated_memory:.1f} MB")

        # Setup optimizer
        optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=0.01)
        criterion = nn.CrossEntropyLoss(ignore_index=0)

        print(f"🚀 Starting fine-tuning...")

        # Training loop
        model.train()
        total_loss = 0.0
        tokens_processed = 0
        start_time = time.time()

        # Add timeout safety
        max_runtime = 60  # 1 minute max
        timeout_start = time.time()

        for step in range(args.training_steps):
            # Safety timeout check
            if time.time() - timeout_start > max_runtime:
                print(f"⏰ LLM fine-tuning timeout after {max_runtime}s - stopping early")
                break
            step_start = time.time()

            # Generate synthetic batch
            input_ids, attention_mask, labels = generate_synthetic_data(
                args.batch_size, args.seq_length, args.vocab_size, device
            )

            # Forward pass
            optimizer.zero_grad()
            logits = model(input_ids, attention_mask)

            # Reshape for loss calculation
            shift_logits = logits[..., :-1, :].contiguous()
            shift_labels = labels[..., 1:].contiguous()

            # Calculate loss
            loss = criterion(
                shift_logits.view(-1, shift_logits.size(-1)),
                shift_labels.view(-1)
            )

            # Backward pass
            loss.backward()

            # Gradient clipping
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)

            # Optimizer step
            optimizer.step()

            # Update statistics
            total_loss += loss.item()
            tokens_processed += args.batch_size * args.seq_length
            step_time = time.time() - step_start

            # Progress reporting
            if (step + 1) % max(1, args.training_steps // 20) == 0:
                elapsed = time.time() - start_time
                avg_loss = total_loss / (step + 1)
                tokens_per_sec = tokens_processed / elapsed if elapsed > 0 else 0
                steps_per_sec = (step + 1) / elapsed if elapsed > 0 else 0

                print(f"⚡ Step {step + 1}/{args.training_steps} - "
                      f"Loss: {loss.item():.4f} - "
                      f"Avg Loss: {avg_loss:.4f} - "
                      f"{tokens_per_sec:,.0f} tokens/sec - "
                      f"{steps_per_sec:.2f} steps/sec")

            # Learning rate scheduling (simple decay)
            if (step + 1) % 100 == 0:
                for param_group in optimizer.param_groups:
                    param_group['lr'] *= 0.99

            # Small delay for system stability
            if step % 50 == 0:
                time.sleep(0.01)

        # Synchronize GPU operations
        if device.type == 'cuda':
            torch.cuda.synchronize()

        total_time = time.time() - start_time

        # Final statistics
        final_avg_loss = total_loss / args.training_steps
        tokens_per_second = tokens_processed / total_time
        steps_per_second = args.training_steps / total_time

        # Estimate computational metrics
        # Rough FLOPs calculation for transformer forward + backward pass
        flops_per_token = 6 * total_params  # Approximate for forward + backward
        total_flops = tokens_processed * flops_per_token
        tflops_per_sec = total_flops / total_time / 1e12

        print(f"\n🎉 LLM fine-tuning completed!")
        print(f"⏱️ Total time: {total_time:.2f} seconds")
        print(f"📊 Training Performance:")
        print(f"   Steps completed: {args.training_steps}")
        print(f"   Steps/second: {steps_per_second:.2f}")
        print(f"   Tokens processed: {tokens_processed:,}")
        print(f"   Tokens/second: {tokens_per_second:,.0f}")
        print(f"   Estimated TFLOPS: {tflops_per_sec:.3f}")
        print(f"\n🧠 Model Training Results:")
        print(f"   Final average loss: {final_avg_loss:.4f}")
        print(f"   Model parameters: {total_params:,}")
        print(f"   Model size: {args.model_size}")
        print(f"   Sequence length: {args.seq_length}")
        print(f"   Batch size: {args.batch_size}")

        # Memory usage
        if device.type == 'cuda':
            memory_allocated = torch.cuda.memory_allocated() / 1024**2
            peak_memory = torch.cuda.max_memory_allocated() / 1024**2
            print(f"💾 GPU Memory - Current: {memory_allocated:.1f} MB, Peak: {peak_memory:.1f} MB")
            torch.cuda.empty_cache()
        elif device.type == 'mps':
            print("🍎 MPS fine-tuning completed")

        # Model evaluation (simple perplexity calculation)
        model.eval()
        with torch.no_grad():
            eval_input_ids, eval_attention_mask, eval_labels = generate_synthetic_data(
                args.batch_size, args.seq_length, args.vocab_size, device
            )
            eval_logits = model(eval_input_ids, eval_attention_mask)

            shift_logits = eval_logits[..., :-1, :].contiguous()
            shift_labels = eval_labels[..., 1:].contiguous()

            eval_loss = criterion(
                shift_logits.view(-1, shift_logits.size(-1)),
                shift_labels.view(-1)
            )
            perplexity = torch.exp(eval_loss)

        print(f"📈 Evaluation Results:")
        print(f"   Evaluation loss: {eval_loss.item():.4f}")
        print(f"   Perplexity: {perplexity.item():.2f}")

    except torch.cuda.OutOfMemoryError:
        print("❌ GPU out of memory! Try reducing --batch-size, --seq-length, or --model-size")
        return 1
    except Exception as e:
        print(f"❌ Error during LLM fine-tuning: {e}")
        return 1

    print(f"✨ LLM fine-tuning benchmark completed successfully!")
    print(f"🤖 Trained {args.model_size} transformer for {args.training_steps} steps")
    return 0

if __name__ == "__main__":
    try:
        exit(main())
    except KeyboardInterrupt:
        print("\n⏹️  LLM fine-tuning interrupted by user")
        exit(0)
    except Exception as e:
        print(f"\n❌ LLM fine-tuning failed: {e}")
        exit(1)