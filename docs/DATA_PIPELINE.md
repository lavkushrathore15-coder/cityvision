# Data Pipeline & Spatio-Temporal Topology

## 1. Frame Ingestion Cycle

For each camera $C_i$ at frame timestamp $t$:
1. Fetch frame $I_t \in \mathbb{R}^{H \times W \times 3}$.
2. If frame skipping is enabled ($t \pmod N == 0$), forward to Vehicle Detector.
3. Detect bounding boxes $\{B_k = (x_1, y_1, x_2, y_2, c, \text{class})\}$.
4. Pass detections into single-camera tracker $\rightarrow$ Tracklets with stable ID $T_k$.
5. For confident tracklets:
   - Crop vehicle patch $V_k$.
   - Extract Re-ID visual embedding vector $\mathbf{e}_k \in \mathbb{R}^{512}$.
   - Attempt ANPR plate detection and OCR $\rightarrow$ Plate string $P_k$ (if visible).
6. Send observation $(C_i, T_k, t, \mathbf{e}_k, P_k)$ to Global Matcher.

---

## 2. Cross-Camera Spatio-Temporal Association Logic

When a vehicle observation $O_A$ arrives from camera $C_A$ at time $t_A$, the matcher compares it against recent observations $O_B$ in the gallery from camera $C_B$ at time $t_B$:

1. **Time-Space Feasibility Filter**:
   $$\Delta t = t_A - t_B$$
   If $\Delta t < \frac{\text{distance}(C_A, C_B)}{v_{\max}}$ or $\Delta t > \Delta t_{\text{max\_window}}$, match is rejected.

2. **ANPR Match**:
   If both have high-confidence plate reads and $\text{Levenshtein}(P_A, P_B) \le 1$, associate with high confidence ($\ge 0.95$).

3. **Re-ID Appearance Cosine Similarity**:
   $$S_{\text{visual}} = \frac{\mathbf{e}_A \cdot \mathbf{e}_B}{\|\mathbf{e}_A\|_2 \|\mathbf{e}_B\|_2}$$
   If $S_{\text{visual}} \ge \tau_{\text{reid}}$ (default $0.75$), candidate matches are merged.

4. **Global ID Assignment**:
   If matched to existing vehicle $\rightarrow$ append waypoint to current trajectory.
   Else $\rightarrow$ generate new `GV-xxxxxx` and register into active gallery.
