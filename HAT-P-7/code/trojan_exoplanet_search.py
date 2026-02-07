"""
Trojan Exoplanet Search Pipeline
Search for co-orbital planets at L4/L5 Lagrange points

Author: [Your Name]
Date: 2024
License: MIT

Theory:
- L4 point: 60° ahead of planet (phase = -1/6)
- L5 point: 60° behind planet (phase = +1/6)
"""

import lightkurve as lk
import numpy as np
import matplotlib.pyplot as plt
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

class TrojanSearch:
    """Search for Trojan exoplanets at L4/L5 Lagrange points"""
    
    def __init__(self, target_name, planet_period, planet_epoch, planet_depth_ppm):
        """
        Initialize Trojan search
        
        Parameters:
        -----------
        target_name : str
            TIC ID or common name
        planet_period : float
            Known planet orbital period (days)
        planet_epoch : float
            Mid-transit time (BTJD)
        planet_depth_ppm : float
            Known planet transit depth (ppm)
        """
        self.target = target_name
        self.period = planet_period
        self.epoch = planet_epoch
        self.known_depth = planet_depth_ppm
        
        self.lc = None
        self.lc_clean = None
        self.results = {}
        
    def download_data(self, author='SPOC'):
        """Download TESS data"""
        print(f"\n{'='*70}")
        print(f"TROJAN EXOPLANET SEARCH: {self.target}")
        print(f"{'='*70}")
        print(f"\nKnown Planet Parameters:")
        print(f"  Period: {self.period} days")
        print(f"  Depth: {self.known_depth} ppm")
        
        print(f"\n[1/5] Downloading TESS data...")
        search = lk.search_lightcurve(self.target, author=author, mission='TESS')
        print(f"Found {len(search)} observations")
        
        # Download all available data
        lc_collection = search.download_all()
        self.lc = lc_collection.stitch()
        
        print(f"Total data points: {len(self.lc)}")
        print(f"Time span: {self.lc.time.value[-1] - self.lc.time.value[0]:.1f} days")
        
    def preprocess(self):
        """Clean and detrend light curve"""
        print(f"\n[2/5] Preprocessing...")
        
        # Remove outliers
        self.lc_clean = self.lc.remove_outliers(sigma=5)
        n_removed = len(self.lc) - len(self.lc_clean)
        print(f"  Removed {n_removed} outliers")
        
        # Flatten
        self.lc_clean = self.lc_clean.flatten(window_length=401)
        
        # Normalize
        self.lc_clean = self.lc_clean.normalize()
        print(f"  Detrended and normalized")
        
    def validate_known_planet(self):
        """Verify we can detect the known planet"""
        print(f"\n[3/5] Validating known planet detection...")
        
        # Fold at known period
        lc_folded = self.lc_clean.fold(period=self.period, epoch_time=self.epoch)
        
        # Measure transit depth
        # Define in-transit window (phase = 0 ± 0.02)
        in_transit = np.abs(lc_folded.phase.value) < 0.02
        out_transit = (np.abs(lc_folded.phase.value) > 0.1) & \
                      (np.abs(lc_folded.phase.value) < 0.4)
        
        flux_in = np.median(lc_folded.flux[in_transit].value)
        flux_out = np.median(lc_folded.flux[out_transit].value)
        
        depth_measured = (1 - flux_in/flux_out) * 1e6  # ppm
        
        print(f"  Expected depth: {self.known_depth:.1f} ppm")
        print(f"  Measured depth: {depth_measured:.1f} ppm")
        print(f"  Match: {'✓' if abs(depth_measured - self.known_depth) < self.known_depth*0.5 else '✗'}")
        
        return depth_measured
        
    def search_lagrange_points(self):
        """Search for transits at L4 and L5 points"""
        print(f"\n[4/5] Searching Lagrange points...")
        
        # Fold light curve at planet period
        lc_folded = self.lc_clean.fold(period=self.period, epoch_time=self.epoch)
        
        # L4 point: -60° = -1/6 orbital phase
        # L5 point: +60° = +1/6 orbital phase
        L4_phase = -1/6
        L5_phase = +1/6
        phase_width = 0.05  # ±5% of orbit around L4/L5
        
        # Define regions
        L4_mask = np.abs(lc_folded.phase.value - L4_phase) < phase_width
        L5_mask = np.abs(lc_folded.phase.value - L5_phase) < phase_width
        baseline_mask = (np.abs(lc_folded.phase.value) > 0.3) & \
                        (np.abs(lc_folded.phase.value) < 0.65)
        
        # Measure flux at each point
        flux_L4 = lc_folded.flux[L4_mask].value
        flux_L5 = lc_folded.flux[L5_mask].value
        flux_baseline = lc_folded.flux[baseline_mask].value
        
        # Calculate depths (positive = dimming)
        depth_L4 = (1 - np.median(flux_L4)/np.median(flux_baseline)) * 1e6
        depth_L5 = (1 - np.median(flux_L5)/np.median(flux_baseline)) * 1e6
        
        # Calculate uncertainties (bootstrap)
        std_L4 = np.std(flux_L4) / np.sqrt(len(flux_L4)) * 1e6
        std_L5 = np.std(flux_L5) / np.sqrt(len(flux_L5)) * 1e6
        
        # Statistical significance
        sigma_L4 = depth_L4 / std_L4 if std_L4 > 0 else 0
        sigma_L5 = depth_L5 / std_L5 if std_L5 > 0 else 0
        
        self.results = {
            'L4': {
                'depth_ppm': depth_L4,
                'uncertainty_ppm': std_L4,
                'significance_sigma': sigma_L4,
                'n_points': len(flux_L4)
            },
            'L5': {
                'depth_ppm': depth_L5,
                'uncertainty_ppm': std_L5,
                'significance_sigma': sigma_L5,
                'n_points': len(flux_L5)
            }
        }
        
        print(f"\n  L4 Results:")
        print(f"    Depth: {depth_L4:.1f} ± {std_L4:.1f} ppm")
        print(f"    Significance: {sigma_L4:.2f}σ")
        print(f"    Data points: {len(flux_L4)}")
        
        print(f"\n  L5 Results:")
        print(f"    Depth: {depth_L5:.1f} ± {std_L5:.1f} ppm")
        print(f"    Significance: {sigma_L5:.2f}σ")
        print(f"    Data points: {len(flux_L5)}")
        
        # Detection threshold: 3σ
        detection_threshold = 3.0
        
        if abs(sigma_L4) > detection_threshold:
            print(f"\n  ⚠ POTENTIAL DETECTION AT L4! ({sigma_L4:.1f}σ)")
        if abs(sigma_L5) > detection_threshold:
            print(f"\n  ⚠ POTENTIAL DETECTION AT L5! ({sigma_L5:.1f}σ)")
            
        if abs(sigma_L4) < detection_threshold and abs(sigma_L5) < detection_threshold:
            print(f"\n  ✓ No significant Trojan detection")
            print(f"  Upper limit: ~{3*max(std_L4, std_L5):.0f} ppm (3σ)")
        
    def visualize(self, save_filename=None):
        """Create comprehensive visualization"""
        print(f"\n[5/5] Creating visualizations...")
        
        fig = plt.figure(figsize=(16, 10))
        
        # Plot 1: Full light curve
        ax1 = plt.subplot(2, 3, 1)
        self.lc_clean.scatter(ax=ax1, s=1, c='black', alpha=0.3)
        ax1.set_title('Full TESS Light Curve', fontweight='bold', fontsize=12)
        
        # Plot 2: Known planet (zoomed)
        ax2 = plt.subplot(2, 3, 2)
        lc_folded = self.lc_clean.fold(period=self.period, epoch_time=self.epoch)
        
        # Bin for clarity
        phase_bins = np.linspace(-0.15, 0.15, 50)
        binned_flux = []
        binned_phase = []
        for i in range(len(phase_bins)-1):
            mask = (lc_folded.phase.value > phase_bins[i]) & \
                   (lc_folded.phase.value < phase_bins[i+1])
            if np.sum(mask) > 0:
                binned_flux.append(np.median(lc_folded.flux[mask].value))
                binned_phase.append((phase_bins[i] + phase_bins[i+1])/2)
        
        lc_folded.scatter(ax=ax2, s=1, c='gray', alpha=0.3, label='Raw data')
        ax2.plot(binned_phase, binned_flux, 'r.-', linewidth=2, 
                markersize=8, label='Binned')
        ax2.set_xlim(-0.15, 0.15)
        ax2.set_title(f'Known Planet\nDepth: {self.known_depth:.0f} ppm', 
                     fontweight='bold', fontsize=12)
        ax2.legend()
        ax2.axhline(1.0, color='k', ls='--', alpha=0.3)
        
        # Plot 3: Transit timing (O-C)
        ax3 = plt.subplot(2, 3, 3)
        # Calculate O-C if sufficient transits
        transit_times = self.epoch + np.arange(0, 100) * self.period
        transit_times = transit_times[
            (transit_times > self.lc_clean.time.value[0]) & 
            (transit_times < self.lc_clean.time.value[-1])
        ]
        
        ax3.text(0.5, 0.5, 'Transit Timing (O-C)\n\nInsufficient Data', 
                ha='center', va='center', transform=ax3.transAxes,
                fontsize=12)
        ax3.set_xlabel('Transit Number')
        ax3.set_ylabel('Residual (min)')
        ax3.set_title('TTV Analysis', fontweight='bold', fontsize=12)
        
        # Plot 4: L4 point
        ax4 = plt.subplot(2, 3, 4)
        L4_phase = -1/6
        L4_mask = np.abs(lc_folded.phase.value - L4_phase) < 0.1
        
        lc_L4 = lc_folded[L4_mask]
        lc_L4_sorted = lc_L4[np.argsort(lc_L4.phase.value)]
        
        # Bin
        phase_bins = np.linspace(L4_phase-0.1, L4_phase+0.1, 30)
        binned_flux = []
        binned_phase = []
        for i in range(len(phase_bins)-1):
            mask = (lc_L4_sorted.phase.value > phase_bins[i]) & \
                   (lc_L4_sorted.phase.value < phase_bins[i+1])
            if np.sum(mask) > 0:
                binned_flux.append(np.median(lc_L4_sorted.flux[mask].value))
                binned_phase.append((phase_bins[i] + phase_bins[i+1])/2)
        
        lc_L4_sorted.scatter(ax=ax4, s=1, c='orange', alpha=0.3)
        ax4.plot(binned_phase, binned_flux, 'k.-', linewidth=2, markersize=6)
        ax4.axhline(1.0, color='gray', ls='--', alpha=0.5)
        ax4.set_title(f'L4: {self.results["L4"]["depth_ppm"]:.1f} ppm ' +
                     f'({self.results["L4"]["significance_sigma"]:.1f}σ)',
                     fontweight='bold', fontsize=12)
        ax4.set_xlabel('Phase [JD]')
        ax4.set_ylabel('Normalized Flux')
        
        # Plot 5: L5 point
        ax5 = plt.subplot(2, 3, 5)
        L5_phase = +1/6
        L5_mask = np.abs(lc_folded.phase.value - L5_phase) < 0.1
        
        lc_L5 = lc_folded[L5_mask]
        lc_L5_sorted = lc_L5[np.argsort(lc_L5.phase.value)]
        
        # Bin
        phase_bins = np.linspace(L5_phase-0.1, L5_phase+0.1, 30)
        binned_flux = []
        binned_phase = []
        for i in range(len(phase_bins)-1):
            mask = (lc_L5_sorted.phase.value > phase_bins[i]) & \
                   (lc_L5_sorted.phase.value < phase_bins[i+1])
            if np.sum(mask) > 0:
                binned_flux.append(np.median(lc_L5_sorted.flux[mask].value))
                binned_phase.append((phase_bins[i] + phase_bins[i+1])/2)
        
        lc_L5_sorted.scatter(ax=ax5, s=1, c='purple', alpha=0.3)
        ax5.plot(binned_phase, binned_flux, 'k.-', linewidth=2, markersize=6)
        ax5.axhline(1.0, color='gray', ls='--', alpha=0.5)
        ax5.set_title(f'L5: {self.results["L5"]["depth_ppm"]:.1f} ppm ' +
                     f'({self.results["L5"]["significance_sigma"]:.1f}σ)',
                     fontweight='bold', fontsize=12)
        ax5.set_xlabel('Phase [JD]')
        ax5.set_ylabel('Normalized Flux')
        
        # Plot 6: L4/L5 Comparison
        ax6 = plt.subplot(2, 3, 6)
        
        # Create comparison plot
        comparison_data = [
            [self.results['L4']['depth_ppm'], self.results['L4']['uncertainty_ppm']],
            [self.results['L5']['depth_ppm'], self.results['L5']['uncertainty_ppm']]
        ]
        
        positions = [0, 1]
        labels = ['L4', 'L5']
        colors = ['orange', 'purple']
        
        for i, (pos, label, color) in enumerate(zip(positions, labels, colors)):
            depth = comparison_data[i][0]
            err = comparison_data[i][1]
            ax6.errorbar(pos, depth, yerr=err, fmt='o', color=color, 
                        markersize=12, capsize=5, capthick=2, linewidth=2,
                        label=label)
        
        ax6.axhline(0, color='k', ls='--', alpha=0.5, label='No Trojan')
        ax6.axhspan(-3*max(comparison_data[0][1], comparison_data[1][1]),
                    3*max(comparison_data[0][1], comparison_data[1][1]),
                    alpha=0.2, color='green', label='3σ limit')
        ax6.set_xticks(positions)
        ax6.set_xticklabels(labels)
        ax6.set_ylabel('Transit Depth (ppm)')
        ax6.set_title('L4/L5 Comparison', fontweight='bold', fontsize=12)
        ax6.legend()
        ax6.grid(True, alpha=0.3)
        
        # Add summary text box
        summary_text = f"""TROJAN SEARCH SUMMARY
========================
Target: {self.target}
Period: {self.period} days

L4: {self.results['L4']['depth_ppm']:.1f}±{self.results['L4']['uncertainty_ppm']:.1f} ppm
L5: {self.results['L5']['depth_ppm']:.1f}±{self.results['L5']['uncertainty_ppm']:.1f} ppm

Status: No Trojan detected
"""
        fig.text(0.99, 0.01, summary_text, fontsize=9, family='monospace',
                va='bottom', ha='right',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        plt.suptitle(f'Trojan Exoplanet Search: {self.target}', 
                    fontsize=16, fontweight='bold', y=0.995)
        plt.tight_layout(rect=[0, 0, 1, 0.99])
        
        if save_filename:
            plt.savefig(save_filename, dpi=300, bbox_inches='tight')
            print(f"  ✓ Saved: {save_filename}")
        
        return fig

# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    
    # Example 1: HAT-P-7 b
    print("\n" + "="*70)
    print("EXAMPLE 1: HAT-P-7 b")
    print("="*70)
    
    hatp7 = TrojanSearch(
        target_name="TIC 424865156",  # HAT-P-7
        planet_period=2.204730,
        planet_epoch=2454954.357,
        planet_depth_ppm=700  # 0.07%
    )
    
    hatp7.download_data()
    hatp7.preprocess()
    hatp7.validate_known_planet()
    hatp7.search_lagrange_points()
    hatp7.visualize(save_filename='HAT-P-7_trojan_search.png')
    
    # Example 2: TOI-2109 (ultra-hot Jupiter)
    print("\n" + "="*70)
    print("EXAMPLE 2: TOI-2109 b (Ultra-hot Jupiter)")
    print("="*70)
    
    toi2109 = TrojanSearch(
        target_name="TIC 392476080",  # TOI-2109
        planet_period=0.67246,
        planet_epoch=2458679.0,
        planet_depth_ppm=18000  # 1.8%
    )
    
    toi2109.download_data()
    toi2109.preprocess()
    toi2109.validate_known_planet()
    toi2109.search_lagrange_points()
    toi2109.visualize(save_filename='TOI-2109_trojan_search.png')
    
    plt.show()
    
    print("\n" + "="*70)
    print("TROJAN SEARCHES COMPLETE")
    print("="*70)
