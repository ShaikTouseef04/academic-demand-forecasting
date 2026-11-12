# Data dictionary

All IDs are immutable strings. Empty `effective_to` means open-ended. Dates use ISO-8601 (`YYYY-MM-DD`); term uses `YYYY-SEASON`.

| Entity / field | Type | Required | Allowed values / units | Uniqueness & validation |
|---|---|---:|---|---|
| Program.program_id | string | Yes | `PRG-000001` | PK; immutable |
| Program.program_name | string | Yes | Human-readable | Not blank |
| Program.department | string | Yes | Department label | Not blank |
| Program.degree_level | enum | Yes | UG, PG | Enum |
| Program.status | enum | Yes | ACTIVE, INACTIVE | Lifecycle |
| Program.effective_from/to | date | from yes, to no | ISO date | to >= from |
| Course.course_id | string | Yes | `CRS-000001` | PK |
| Course.program_id | string | Yes | Program ID | FK -> Program |
| Course.course_code | string | Yes | C + 4 digits | Unique |
| Course.course_name | string | Yes | Text | Not blank |
| Course.course_type | enum | Yes | CORE, ELECTIVE | Enum |
| Course.credits | integer | Yes | 1-6 credits | Positive bounded |
| Course.required_skill | string | Yes | SKILL-01..12 | Must match skill vocabulary |
| Course.weekly_hours | integer | Yes | Hours/week | > 0 |
| Course.status | enum | Yes | ACTIVE, INACTIVE | Lifecycle |
| Prerequisite.prerequisite_id | string | Yes | PRE-000001 | PK |
| Prerequisite.course_id | string | Yes | Course ID | FK -> Course |
| Prerequisite.required_course_id | string | Yes | Course ID | FK -> Course; not same course |
| Prerequisite.minimum_grade | enum | Yes | A..F; generated C | Enum |
| Prerequisite.effective_from/to | date | from yes, to no | ISO date | to >= from |
| StudentPlan.student_plan_id | string | Yes | STP-000001 | PK |
| StudentPlan.student_ref | string | Yes | Synthetic STU reference | Unique; no real PII |
| StudentPlan.program_id | string | Yes | Program ID | FK -> Program |
| StudentPlan.term | string | Yes | YYYY-SEASON | Term format |
| StudentPlan.year_of_study | integer | Yes | 1-8 | Range |
| StudentPlan.plan_status | enum | Yes | APPROVED, DRAFT, CANCELLED | Lifecycle |
| RegistrationInterest.registration_interest_id | string | Yes | INT-000001 | PK |
| RegistrationInterest.student_plan_id | string | Yes | StudentPlan ID | FK -> StudentPlan |
| RegistrationInterest.course_id | string | Yes | Course ID | FK -> Course |
| RegistrationInterest.term/date | string/date | Yes | Term / ISO date | Date consistent with term |
| RegistrationInterest.priority | integer | Yes | 1-3 | Range |
| RegistrationInterest.interest_status | enum | Yes | CONFIRMED, WITHDRAWN | Lifecycle |
| Faculty.faculty_id | string | Yes | `FAC-000001` | PK |
| Faculty.faculty_name | string | Yes | Synthetic name | Not blank |
| Faculty.employment_type | enum | Yes | FULL_TIME, PART_TIME | Enum |
| Faculty.weekly_workload_limit | integer | Yes | Hours/week | > 0 |
| Faculty.status | enum | Yes | ACTIVE, INACTIVE | Lifecycle |
| FacultySkill.faculty_skill_id | string | Yes | FSK-000001 | PK |
| FacultySkill.faculty_id | string | Yes | Faculty ID | FK -> Faculty |
| FacultySkill.skill_code | string | Yes | SKILL-01..12 | Unique with faculty/effective_from |
| FacultySkill.proficiency | enum | Yes | INTERMEDIATE, ADVANCED, EXPERT | Enum |
| FacultySkill.effective_from/to | date | from yes, to no | ISO date | to >= from |
| Availability.availability_id | string | Yes | AVL-000001 | PK |
| Availability.faculty_id | string | Yes | Faculty ID | FK -> Faculty |
| Availability.term/day | string | Yes | Term; MON..FRI | Unique faculty/term/day |
| Availability.available/leave_flag | boolean | Yes | true/false | Leave excludes allocation |
| Room.room_id | string | Yes | ROM-000001 | PK |
| Room.building/name | string | Yes | Text | Room name unique in building |
| Room.capacity | integer | Yes | Seats | > 0 |
| Room.room_type | enum | Yes | LECTURE, LAB | Enum |
| Room.status | enum | Yes | ACTIVE, INACTIVE | Lifecycle |
| Section.section_id | string | Yes | `SEC-2026-000001` | PK |
| Section.course_id / room_id | string | Yes | IDs | FKs |
| Section.term | string | Yes | YYYY-SEASON | Term |
| Section.capacity / planned_enrollment | integer | Yes | Seats/students | 0 < enrollment <= capacity <= room capacity |
| Section.section_status | enum | Yes | PROPOSED, APPROVED, CANCELLED | Lifecycle |
| WorkloadAssignment.workload_assignment_id | string | Yes | `WLA-2026-000001` | PK |
| WorkloadAssignment.section_id/faculty_id | string | Yes | IDs | FKs; unique section/faculty |
| WorkloadAssignment.weekly_hours | integer | Yes | Hours/week | > 0; faculty total <= limit |
| WorkloadAssignment.assignment_status | enum | Yes | PROPOSED, APPROVED, REJECTED | Lifecycle |

## Relationships and cardinality
- Program 1:N Course; Program 1:N StudentPlan.
- Course 1:N Prerequisite (as target) and 1:N Prerequisite (as required course).
- StudentPlan 1:N RegistrationInterest; Course 1:N RegistrationInterest. Together StudentPlan and Course are N:M through RegistrationInterest.
- Faculty 1:N FacultySkill and 1:N Availability.
- Course 1:N Section; Room 1:N Section.
- Section 1:N WorkloadAssignment; Faculty 1:N WorkloadAssignment. Together Section and Faculty are N:M through WorkloadAssignment.
- Availability is optional per faculty/day; prerequisite is optional per course; workload assignment is optional for an unstaffed proposed section.
- Effective dates apply to Program, Prerequisite and FacultySkill. State changes are append-only in StateEvent.

## Rules / derived fields
Forecast = ceiling(mean of confirmed historical interest counts over configured historical terms * 1.12). Current target-term registrations are excluded from the forecast feature window. Section count and sizes derive from forecast and room capacities. Faculty choice requires matching skill, available status, no leave, and remaining weekly workload. Unmet demand is emitted with a reason when no eligible instructor or room/section capacity exists.
