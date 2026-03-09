"""
Seed script — populates the database with a realistic ML curriculum.

Graph structure (prerequisites → concept):
  Linear Algebra ──────────────────────────────────────┐
  Calculus ────────────────────────────────────────────┤
  Probability & Statistics ────────────────────────────┤
                                                        ▼
  Linear Algebra ──────────────────────────────────────► Matrix Multiplication
  Calculus ──────────────────────────────────────────► Partial Derivatives
  Partial Derivatives ────────────────────────────────► Chain Rule
  Probability & Statistics ────────────────────────────► Distributions & Sampling
  Matrix Multiplication + Chain Rule ─────────────────► Backpropagation
  Backpropagation ─────────────────────────────────────► Gradient Descent
  Gradient Descent ────────────────────────────────────► Neural Network Basics
  Neural Network Basics + Distributions ──────────────► Loss Functions
  Loss Functions + Gradient Descent ──────────────────► Training a Neural Network
  Training a Neural Network ──────────────────────────► Regularization
  Training a Neural Network ──────────────────────────► Optimizers (Adam, SGD)
  Neural Network Basics ───────────────────────────────► Convolutional Neural Nets
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from database import init_db, get_db
import crud

CONCEPTS = [
    # Foundations — mastered by default so learner starts mid-journey
    dict(name="Linear Algebra",              description="Vectors, matrices, linear transformations, eigenvalues.", difficulty=2),
    dict(name="Calculus",                    description="Limits, derivatives, integrals, fundamental theorem.", difficulty=2),
    dict(name="Probability & Statistics",    description="Probability theory, expectation, variance, common distributions.", difficulty=2),

    # Core Math
    dict(name="Matrix Multiplication",       description="Dot products, matrix-vector products, dimensionality.", difficulty=2),
    dict(name="Partial Derivatives",         description="Derivatives of multi-variable functions, gradient vectors.", difficulty=3),
    dict(name="Chain Rule",                  description="Derivative of composed functions — the backbone of backprop.", difficulty=3),
    dict(name="Distributions & Sampling",    description="Normal, Bernoulli, Softmax as a distribution, KL divergence.", difficulty=3),

    # ML Core
    dict(name="Backpropagation",             description="Compute gradients via reverse-mode automatic differentiation.", difficulty=4),
    dict(name="Gradient Descent",            description="Iterative optimization using gradients to minimize loss.", difficulty=3),
    dict(name="Neural Network Basics",       description="Layers, activations (ReLU, sigmoid), forward pass.", difficulty=3),
    dict(name="Loss Functions",              description="MSE, cross-entropy, their derivatives and use-cases.", difficulty=3),
    dict(name="Training a Neural Network",   description="Forward + backward pass, mini-batch SGD, epoch loop.", difficulty=4),

    # Advanced
    dict(name="Regularization",              description="L1/L2 regularization, dropout, batch normalization.", difficulty=4),
    dict(name="Optimizers (Adam, SGD)",      description="Momentum, RMSProp, Adam — adaptive learning rate methods.", difficulty=4),
    dict(name="Convolutional Neural Nets",   description="Convolution operation, pooling, receptive field, CNNs for vision.", difficulty=5),
]

PREREQUISITES = [
    # Matrix Multiplication
    ("Matrix Multiplication",       "Linear Algebra"),

    # Partial Derivatives
    ("Partial Derivatives",         "Calculus"),

    # Chain Rule
    ("Chain Rule",                  "Partial Derivatives"),

    # Distributions
    ("Distributions & Sampling",    "Probability & Statistics"),

    # Backpropagation
    ("Backpropagation",             "Chain Rule"),
    ("Backpropagation",             "Matrix Multiplication"),

    # Gradient Descent
    ("Gradient Descent",            "Backpropagation"),

    # Neural Network Basics
    ("Neural Network Basics",       "Gradient Descent"),
    ("Neural Network Basics",       "Matrix Multiplication"),

    # Loss Functions
    ("Loss Functions",              "Neural Network Basics"),
    ("Loss Functions",              "Distributions & Sampling"),

    # Training a Neural Network
    ("Training a Neural Network",   "Loss Functions"),
    ("Training a Neural Network",   "Gradient Descent"),

    # Regularization
    ("Regularization",              "Training a Neural Network"),

    # Optimizers
    ("Optimizers (Adam, SGD)",      "Gradient Descent"),
    ("Optimizers (Adam, SGD)",      "Training a Neural Network"),

    # CNNs
    ("Convolutional Neural Nets",   "Neural Network Basics"),
]

# Simulate a learner who has finished foundations and started ML core
INITIAL_MASTERY: dict[str, int] = {
    "Linear Algebra":           3,   # Mastered
    "Calculus":                 3,   # Mastered
    "Probability & Statistics": 3,   # Mastered
    "Matrix Multiplication":    3,   # Mastered
    "Partial Derivatives":      3,   # Mastered
    "Chain Rule":               2,   # Practicing
    "Distributions & Sampling": 2,   # Practicing
    "Backpropagation":          1,   # Learning
    "Gradient Descent":         0,   # Not started
}


def seed():
    init_db()
    name_to_id: dict[str, int] = {}

    with get_db() as conn:
        # Clear existing data
        conn.execute("DELETE FROM prerequisites")
        conn.execute("DELETE FROM progress")
        conn.execute("DELETE FROM concepts")

        # Insert concepts
        for c in CONCEPTS:
            result = crud.create_concept(conn, c["name"], c["description"], c["difficulty"])
            name_to_id[c["name"]] = result.id
            print(f"  ✓ Created: {c['name']} (id={result.id})")

        # Insert prerequisite links
        for concept_name, prereq_name in PREREQUISITES:
            cid  = name_to_id[concept_name]
            pid  = name_to_id[prereq_name]
            crud.add_prerequisite(conn, cid, pid)

        # Set initial mastery
        for name, level in INITIAL_MASTERY.items():
            crud.set_mastery(conn, name_to_id[name], level)
            print(f"  ✓ Mastery [{level}] → {name}")

    print(f"\n✅ Seeded {len(CONCEPTS)} concepts, {len(PREREQUISITES)} prerequisite links.")
    print(f"   Simulated learner progress for {len(INITIAL_MASTERY)} concepts.")


if __name__ == "__main__":
    seed()
