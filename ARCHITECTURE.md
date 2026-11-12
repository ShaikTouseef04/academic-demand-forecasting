# Architecture and decision logic

1. `generate()` creates parent/master tables before dependent rows.
2. RegistrationInterest is an event-like fact table with term and status.
3. Forecast uses three configured historical terms; target term is excluded.
4. Section capacity is bounded by selected room capacity.
5. Faculty allocation requires matching `required_skill`, availability, no leave and sufficient remaining workload.
6. Unstaffed demand and room shortfalls become explicit unmet-demand rows.
7. `ground_truth` is generated separately after baseline decisions and is not joined into model features.
8. `validate()` checks key uniqueness, foreign keys, workload and room capacity.

## Limitations / next production steps
- This is a transparent baseline heuristic, not a trained ML model; the forecast baseline is a moving historical mean with a documented uplift.
- Add academic calendar slot conflicts, student-level prerequisite completion, room equipment, instructor contract caps, and approval events for production.
- Extend StateEvent writes when sections/assignments move from PROPOSED to APPROVED/REJECTED.
