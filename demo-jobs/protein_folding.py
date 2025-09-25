#!/usr/bin/env python3
"""
Protein Folding Simulation - Molecular Dynamics Benchmark
Simulates protein structure prediction using simplified molecular dynamics
Mac-compatible with CUDA/MPS acceleration
"""

import torch
import torch.nn.functional as F
import math
import time
import argparse

def initialize_protein_chain(num_residues, device):
    """
    Initialize a random protein chain with backbone atoms (N, CA, C)
    """
    # Generate random initial positions in 3D space
    positions = torch.randn(num_residues, 3, 3, device=device, dtype=torch.float32)  # [residues, atoms, xyz]

    # Apply some constraints to make it more realistic
    # Set approximate bond lengths and angles
    for i in range(num_residues - 1):
        # Connect residues with peptide bonds (simplified)
        positions[i + 1, 0] = positions[i, 2] + torch.randn(3, device=device) * 0.1  # Connect C to next N

    # Initialize velocities (Maxwell-Boltzmann distribution)
    velocities = torch.randn_like(positions) * 0.01

    return positions, velocities

def calculate_bond_forces(positions, bond_strength=100.0):
    """
    Calculate forces from covalent bonds (simplified harmonic potential)
    """
    num_residues = positions.shape[0]
    forces = torch.zeros_like(positions)

    # Bond length targets (in Angstroms, simplified)
    target_lengths = {
        'N-CA': 1.46,
        'CA-C': 1.52,
        'C-N': 1.33  # peptide bond
    }

    # Intra-residue bonds (N-CA, CA-C)
    for i in range(num_residues):
        # N-CA bond
        n_pos = positions[i, 0]  # N atom
        ca_pos = positions[i, 1]  # CA atom
        c_pos = positions[i, 2]   # C atom

        # N-CA bond force
        n_ca_vec = ca_pos - n_pos
        n_ca_dist = torch.norm(n_ca_vec)
        n_ca_force = bond_strength * (n_ca_dist - target_lengths['N-CA']) * n_ca_vec / (n_ca_dist + 1e-8)

        forces[i, 0] += n_ca_force
        forces[i, 1] -= n_ca_force

        # CA-C bond force
        ca_c_vec = c_pos - ca_pos
        ca_c_dist = torch.norm(ca_c_vec)
        ca_c_force = bond_strength * (ca_c_dist - target_lengths['CA-C']) * ca_c_vec / (ca_c_dist + 1e-8)

        forces[i, 1] += ca_c_force
        forces[i, 2] -= ca_c_force

    # Inter-residue peptide bonds (C-N)
    for i in range(num_residues - 1):
        c_pos = positions[i, 2]      # C atom of residue i
        n_pos = positions[i + 1, 0]  # N atom of residue i+1

        c_n_vec = n_pos - c_pos
        c_n_dist = torch.norm(c_n_vec)
        c_n_force = bond_strength * (c_n_dist - target_lengths['C-N']) * c_n_vec / (c_n_dist + 1e-8)

        forces[i, 2] += c_n_force
        forces[i + 1, 0] -= c_n_force

    return forces

def calculate_nonbonded_forces(positions, epsilon=1.0, sigma=3.5, cutoff=12.0):
    """
    Calculate non-bonded forces using Lennard-Jones potential
    """
    num_residues = positions.shape[0]
    forces = torch.zeros_like(positions)

    # Flatten positions for pairwise calculations
    all_positions = positions.view(-1, 3)  # [num_atoms, 3]
    num_atoms = all_positions.shape[0]

    # Calculate pairwise distances and forces
    for i in range(num_atoms):
        pos_i = all_positions[i]

        # Vectorized distance calculation for all other atoms
        pos_others = all_positions[i+1:]
        if pos_others.shape[0] == 0:
            continue

        distances_vec = pos_others - pos_i.unsqueeze(0)
        distances = torch.norm(distances_vec, dim=1)

        # Apply cutoff
        within_cutoff = distances < cutoff
        if not torch.any(within_cutoff):
            continue

        # Filter by cutoff
        filtered_distances = distances[within_cutoff]
        filtered_vec = distances_vec[within_cutoff]

        # Lennard-Jones potential: V = 4*epsilon*((sigma/r)^12 - (sigma/r)^6)
        # Force: F = -dV/dr = 24*epsilon/r * ((sigma/r)^6 - 2*(sigma/r)^12)

        sigma_over_r = sigma / (filtered_distances + 1e-8)
        sigma6 = sigma_over_r ** 6
        sigma12 = sigma6 ** 2

        # Calculate force magnitude
        force_magnitude = 24 * epsilon / (filtered_distances + 1e-8) * (sigma6 - 2 * sigma12)

        # Calculate force vectors
        force_vectors = force_magnitude.unsqueeze(1) * filtered_vec / (filtered_distances.unsqueeze(1) + 1e-8)

        # Apply forces (Newton's 3rd law)
        all_positions_forces = torch.zeros_like(all_positions)
        all_positions_forces[i] -= torch.sum(force_vectors, dim=0)

        # Distribute forces to other atoms
        other_indices = torch.arange(i+1, num_atoms, device=positions.device)[within_cutoff]
        for j, force_vec in zip(other_indices, force_vectors):
            all_positions_forces[j] += force_vec

        forces += all_positions_forces.view_as(positions)

    return forces

def calculate_electrostatic_forces(positions, charges, dielectric=80.0):
    """
    Calculate electrostatic forces using Coulomb's law
    """
    num_residues = positions.shape[0]
    forces = torch.zeros_like(positions)

    # Simplified charge assignment (based on residue type simulation)
    # In reality, this would depend on amino acid types
    if charges is None:
        charges = torch.randn(num_residues, 3, device=positions.device) * 0.5

    # Coulomb constant (simplified units)
    ke = 8.99e9 / (dielectric * 1e10)  # Adjusted for Angstrom units

    all_positions = positions.view(-1, 3)
    all_charges = charges.view(-1)
    num_atoms = all_positions.shape[0]

    for i in range(num_atoms):
        if abs(all_charges[i]) < 1e-6:
            continue

        pos_i = all_positions[i]
        charge_i = all_charges[i]

        # Calculate forces with all other charged atoms
        for j in range(i + 1, num_atoms):
            if abs(all_charges[j]) < 1e-6:
                continue

            pos_j = all_positions[j]
            charge_j = all_charges[j]

            r_vec = pos_j - pos_i
            r_dist = torch.norm(r_vec) + 1e-8

            # Coulomb force
            force_magnitude = ke * charge_i * charge_j / (r_dist ** 2)
            force_vector = force_magnitude * r_vec / r_dist

            # Apply forces
            all_forces = torch.zeros_like(all_positions)
            all_forces[i] -= force_vector
            all_forces[j] += force_vector

            forces += all_forces.view_as(positions)

    return forces

def calculate_secondary_structure_energy(positions, target_phi=-60.0, target_psi=-45.0):
    """
    Calculate energy bias toward alpha-helix formation (simplified)
    """
    num_residues = positions.shape[0]
    energy = 0.0
    forces = torch.zeros_like(positions)

    # This is a simplified approach - real secondary structure calculation
    # would involve proper dihedral angle calculations
    for i in range(1, num_residues - 1):
        # Calculate pseudo dihedral angles
        vec1 = positions[i, 1] - positions[i-1, 1]  # CA[i] - CA[i-1]
        vec2 = positions[i+1, 1] - positions[i, 1]  # CA[i+1] - CA[i]

        # Simplified angle-based energy
        dot_product = torch.dot(vec1, vec2)
        angle = torch.acos(torch.clamp(dot_product / (torch.norm(vec1) * torch.norm(vec2) + 1e-8), -1, 1))

        # Bias toward alpha-helix geometry
        target_angle = math.radians(108)  # Approximate alpha-helix CA-CA-CA angle
        angle_diff = angle - target_angle
        energy += 0.5 * angle_diff ** 2

    return energy

def molecular_dynamics_step(positions, velocities, forces, dt=0.001, mass=1.0):
    """
    Perform one step of molecular dynamics using Verlet integration
    """
    # Verlet integration
    # x(t+dt) = x(t) + v(t)*dt + 0.5*a(t)*dt^2
    # v(t+dt) = v(t) + 0.5*(a(t) + a(t+dt))*dt

    acceleration = forces / mass

    # Update positions
    new_positions = positions + velocities * dt + 0.5 * acceleration * dt ** 2

    # Update velocities (using current acceleration, will be corrected with new forces)
    new_velocities = velocities + acceleration * dt

    return new_positions, new_velocities

def calculate_rmsd(positions1, positions2):
    """
    Calculate Root Mean Square Deviation between two structures
    """
    diff = positions1 - positions2
    rmsd = torch.sqrt(torch.mean(diff ** 2))
    return rmsd

def main():
    parser = argparse.ArgumentParser(description='Protein Folding Simulation')
    parser.add_argument('--residues', type=int, default=100, help='Number of amino acid residues')
    parser.add_argument('--steps', type=int, default=10000, help='Number of MD simulation steps')
    parser.add_argument('--device', type=str, default='auto', help='Device to use')
    parser.add_argument('--dt', type=float, default=0.001, help='Time step size (ps)')
    parser.add_argument('--save-frequency', type=int, default=500, help='Save structure every N steps')
    parser.add_argument('--temperature', type=float, default=300.0, help='Simulation temperature (K)')
    args = parser.parse_args()

    print(f"🧬 Starting Protein Folding Simulation")
    print(f"   Residues: {args.residues}")
    print(f"   MD steps: {args.steps}")
    print(f"   Time step: {args.dt} ps")
    print(f"   Temperature: {args.temperature} K")

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

    # Memory estimation
    num_atoms = args.residues * 3  # N, CA, C atoms per residue
    memory_per_atom = 3 * 4 * 3  # 3 coordinates * 4 bytes * 3 (pos, vel, force)
    estimated_memory = (num_atoms * memory_per_atom) / (1024 * 1024)
    print(f"💾 Estimated memory usage: {estimated_memory:.1f} MB")

    try:
        # Initialize protein structure
        print(f"🏗️ Initializing protein chain...")
        positions, velocities = initialize_protein_chain(args.residues, device)
        initial_positions = positions.clone()

        # Initialize charges (simplified)
        charges = torch.randn(args.residues, 3, device=device) * 0.2

        print(f"⚗️ Starting molecular dynamics simulation...")

        # Simulation variables
        total_energy_history = []
        rmsd_history = []
        step_times = []
        start_time = time.time()

        for step in range(args.steps):
            step_start = time.time()

            # Calculate all forces
            bond_forces = calculate_bond_forces(positions)
            nonbonded_forces = calculate_nonbonded_forces(positions)
            electrostatic_forces = calculate_electrostatic_forces(positions, charges)

            total_forces = bond_forces + nonbonded_forces + electrostatic_forces

            # Apply temperature control (simple velocity scaling)
            if step % 100 == 0:
                # Calculate current kinetic energy and temperature
                kinetic_energy = 0.5 * torch.sum(velocities ** 2)
                current_temp = kinetic_energy / (1.5 * num_atoms * 8.314e-3)  # Boltzmann constant

                if current_temp > 0:
                    temp_scaling = math.sqrt(args.temperature / current_temp.item())
                    velocities *= min(temp_scaling, 1.2)  # Limit scaling

            # Perform MD step
            positions, velocities = molecular_dynamics_step(positions, velocities, total_forces, args.dt)

            # Calculate energies and RMSD
            if step % args.save_frequency == 0:
                # Calculate total energy (simplified)
                kinetic_energy = 0.5 * torch.sum(velocities ** 2)
                secondary_energy = calculate_secondary_structure_energy(positions)
                total_energy = kinetic_energy + secondary_energy

                # Calculate RMSD from initial structure
                rmsd = calculate_rmsd(positions, initial_positions)

                total_energy_history.append(total_energy.item())
                rmsd_history.append(rmsd.item())

                elapsed = time.time() - start_time
                steps_per_sec = (step + 1) / elapsed if elapsed > 0 else 0

                print(f"⚡ Step {step}/{args.steps} - "
                      f"Energy: {total_energy:.2f} - "
                      f"RMSD: {rmsd:.3f} Å - "
                      f"{steps_per_sec:.1f} steps/sec")

            step_times.append(time.time() - step_start)

            # Small delay for system stability
            if step % 1000 == 0:
                time.sleep(0.01)

        # Synchronize GPU operations
        if device.type == 'cuda':
            torch.cuda.synchronize()

        total_time = time.time() - start_time

        # Final analysis
        final_rmsd = calculate_rmsd(positions, initial_positions)
        avg_step_time = sum(step_times) / len(step_times)
        steps_per_second = args.steps / total_time

        # Calculate folding metrics
        if len(rmsd_history) > 1:
            rmsd_change = abs(rmsd_history[-1] - rmsd_history[0])
            energy_change = abs(total_energy_history[-1] - total_energy_history[0])
        else:
            rmsd_change = 0
            energy_change = 0

        # Estimate computational throughput
        total_force_calculations = args.steps * args.residues ** 2  # Approximate
        force_calcs_per_sec = total_force_calculations / total_time

        print(f"\n🎉 Protein folding simulation completed!")
        print(f"⏱️ Total time: {total_time:.2f} seconds")
        print(f"📊 Performance:")
        print(f"   Steps completed: {args.steps}")
        print(f"   Steps/second: {steps_per_second:.1f}")
        print(f"   Avg step time: {avg_step_time*1000:.2f} ms")
        print(f"   Force calculations/sec: {force_calcs_per_sec:,.0f}")
        print(f"\n🧬 Folding Results:")
        print(f"   Final RMSD: {final_rmsd:.3f} Å")
        print(f"   RMSD change: {rmsd_change:.3f} Å")
        print(f"   Energy change: {energy_change:.2f}")
        print(f"   Protein length: {args.residues} residues")
        print(f"   Simulation time: {args.steps * args.dt:.3f} ps")

        # Memory cleanup
        if device.type == 'cuda':
            memory_allocated = torch.cuda.memory_allocated() / 1024**2
            peak_memory = torch.cuda.max_memory_allocated() / 1024**2
            print(f"💾 GPU Memory - Current: {memory_allocated:.1f} MB, Peak: {peak_memory:.1f} MB")
            torch.cuda.empty_cache()
        elif device.type == 'mps':
            print("🍎 MPS folding simulation completed")

    except torch.cuda.OutOfMemoryError:
        print("❌ GPU out of memory! Try reducing --residues parameter")
        return 1
    except Exception as e:
        print(f"❌ Error during protein folding simulation: {e}")
        return 1

    print(f"✨ Protein folding benchmark completed successfully!")
    print(f"🧬 Simulated {args.residues}-residue protein for {args.steps} MD steps")
    return 0

if __name__ == "__main__":
    try:
        exit(main())
    except KeyboardInterrupt:
        print("\n⏹️  Protein folding interrupted by user")
        exit(0)
    except Exception as e:
        print(f"\n❌ Protein folding failed: {e}")
        exit(1)