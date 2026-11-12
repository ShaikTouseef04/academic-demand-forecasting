from __future__ import annotations
import argparse, json, hashlib
from pathlib import Path
from collections import defaultdict
import numpy as np
import pandas as pd

def make_id(prefix, n, width=6):
    return f"{prefix}-{n:0{width}d}"

def generate(config, outdir):
    rng = np.random.default_rng(config["seed"])
    v = config["volumes"][config["scale"]]
    out = Path(outdir); out.mkdir(parents=True, exist_ok=True)
    terms = config["history_terms"] + [config["target_term"]]

    # 1. Master data
    programs = []
    for i in range(1, v["programs"]+1):
        programs.append({"program_id":make_id("PRG",i), "program_name":f"Program {i:03d}",
                         "department":f"Department {(i-1)%10+1:02d}", "degree_level":rng.choice(["UG","PG"]),
                         "status":"ACTIVE", "effective_from":"2024-07-01", "effective_to":""})
    programs = pd.DataFrame(programs)

    courses=[]
    for i in range(1, v["courses"]+1):
        p = programs.iloc[(i-1)%len(programs)]
        courses.append({"course_id":make_id("CRS",i), "program_id":p.program_id,
                        "course_code":f"C{i:04d}", "course_name":f"Course {i:04d}",
                        "course_type":"ELECTIVE" if i%7==0 else "CORE",
                        "credits":int(rng.choice([2,3,4])), "required_skill":f"SKILL-{(i-1)%12+1:02d}",
                        "weekly_hours":int(rng.choice([2,3,4])), "status":"ACTIVE"})
    courses=pd.DataFrame(courses)

    prerequisites=[]
    for i in range(1, len(courses)+1):
        if i>5 and i%4==0:
            prerequisites.append({"prerequisite_id":make_id("PRE",len(prerequisites)+1),
                "course_id":make_id("CRS",i), "required_course_id":make_id("CRS",i-2),
                "minimum_grade":"C", "effective_from":"2024-07-01", "effective_to":""})
    prerequisites=pd.DataFrame(prerequisites, columns=["prerequisite_id","course_id","required_course_id","minimum_grade","effective_from","effective_to"])

    # 2. People, plans, skills, availability and rooms
    faculty=[]
    for i in range(1,v["faculty"]+1):
        faculty.append({"faculty_id":make_id("FAC",i), "faculty_name":f"Faculty {i:04d}",
                        "employment_type":rng.choice(["FULL_TIME","PART_TIME"]), "weekly_workload_limit":int(rng.choice([8,10,12,14])),
                        "status":"ACTIVE"})
    faculty=pd.DataFrame(faculty)

    skills=[]
    for _, f in faculty.iterrows():
        for skill in rng.choice([f"SKILL-{x:02d}" for x in range(1,13)], size=int(rng.integers(2,5)), replace=False):
            skills.append({"faculty_skill_id":make_id("FSK",len(skills)+1),"faculty_id":f.faculty_id,
                           "skill_code":skill,"proficiency":rng.choice(["INTERMEDIATE","ADVANCED","EXPERT"]),
                           "effective_from":"2025-01-01","effective_to":""})
    skills=pd.DataFrame(skills)

    availability=[]
    for _, f in faculty.iterrows():
        for day in ["MON","TUE","WED","THU","FRI"]:
            availability.append({"availability_id":make_id("AVL",len(availability)+1),"faculty_id":f.faculty_id,
                                 "term":config["target_term"],"day":day,"available":bool(rng.random()>.12),
                                 "leave_flag":bool(rng.random()<.035)})
    availability=pd.DataFrame(availability)

    rooms=[]
    for i in range(1,v["rooms"]+1):
        rooms.append({"room_id":make_id("ROM",i),"building":f"Building {(i-1)%8+1}",
                      "room_name":f"Room {i:03d}","capacity":int(rng.choice([25,30,40,50,60,80])),
                      "room_type":"LAB" if i%5==0 else "LECTURE","status":"ACTIVE"})
    rooms=pd.DataFrame(rooms)

    plans=[]
    for i in range(1,v["student_plans"]+1):
        p = programs.iloc[int(rng.integers(0,len(programs)))]
        plans.append({"student_plan_id":make_id("STP",i),"student_ref":f"STU-{i:07d}",
                      "program_id":p.program_id,"term":config["target_term"],
                      "year_of_study":int(rng.integers(1,5)),"plan_status":"APPROVED"})
    plans=pd.DataFrame(plans)

    # Interests: historical observations plus current demand, generated from valid program-course mapping.
    interests=[]
    courses_by_program={k:g.course_id.tolist() for k,g in courses.groupby("program_id")}
    for term in terms:
        for _, plan in plans.iterrows():
            eligible=courses_by_program[plan.program_id]
            count=int(rng.integers(2,min(6,len(eligible))+1))
            selected=rng.choice(eligible,size=count,replace=False)
            for cid in selected:
                # popular electives are intentionally more likely to attract interest
                ctype=courses.loc[courses.course_id==cid,"course_type"].iloc[0]
                weight=1.7 if ctype=="ELECTIVE" and int(cid[-6:])%3==0 else 1.0
                if rng.random() < min(.95,.55*weight):
                    interests.append({"registration_interest_id":make_id("INT",len(interests)+1),
                      "student_plan_id":plan.student_plan_id,"course_id":cid,"term":term,
                      "interest_date":f"{term[:4]}-01-15","priority":int(rng.integers(1,4)),
                      "interest_status":"CONFIRMED" if rng.random()>.08 else "WITHDRAWN"})
    interests=pd.DataFrame(interests)

    # 3. Forecast from historical term windows; current-term interest is not used to train.
    hist=interests[interests.term.isin(config["history_terms"]) & (interests.interest_status=="CONFIRMED")]
    forecast=hist.groupby("course_id").agg(history_mean=("registration_interest_id","count")).reset_index()
    forecast["history_windows"]=len(config["history_terms"])
    forecast["forecast_enrollment"]=np.ceil(forecast.history_mean/len(config["history_terms"])*1.12).astype(int)
    forecast=forecast[["course_id","history_mean","history_windows","forecast_enrollment"]]
    forecast=courses[["course_id"]].merge(forecast,on="course_id",how="left").fillna({"history_mean":0,"history_windows":len(config["history_terms"]),"forecast_enrollment":0})
    forecast["forecast_enrollment"]=forecast.forecast_enrollment.astype(int)
    forecast["forecast_method"]="3_TERM_MEAN_X_1.12"

    # 4. Propose sections from forecast, room capacities and course requirements.
    section_rows=[]; assignment_rows=[]; unmet_rows=[]
    fac_skill={fid:set(g.skill_code) for fid,g in skills.groupby("faculty_id")}
    fac_load=defaultdict(int)
    fac_limit=dict(zip(faculty.faculty_id,faculty.weekly_workload_limit))
    available_fac=set(availability[(availability.available)&(~availability.leave_flag)].faculty_id)
    room_list=rooms[rooms.status=="ACTIVE"].sort_values("capacity").to_dict("records")
    for _, c in courses.iterrows():
        demand=int(forecast.loc[forecast.course_id==c.course_id,"forecast_enrollment"].iloc[0])
        if demand<=0: continue
        suitable=[r for r in room_list if r["capacity"]>=min(demand,25) and (c.required_skill is None or True)]
        # section capacity is constrained by room capacity; one section may be insufficient.
        max_cap=max([r["capacity"] for r in suitable],default=0)
        sections_needed=int(np.ceil(demand/max(max_cap,1)))
        allocated=0
        for s in range(sections_needed):
            remaining=demand-allocated
            room=next((r for r in room_list if r["capacity"]>=min(remaining,25)),None)
            if room is None: break
            cap=min(room["capacity"],remaining)
            candidates=[fid for fid in available_fac if c.required_skill in fac_skill.get(fid,set())
                        and fac_load[fid]+int(c.weekly_hours)<=fac_limit[fid]]
            candidates.sort(key=lambda x:(fac_load[x],x))
            fid=candidates[0] if candidates else ""
            sid=f"SEC-2026-{len(section_rows)+1:06d}"
            section_rows.append({"section_id":sid,"course_id":c.course_id,"term":config["target_term"],
                                 "room_id":room["room_id"],"capacity":int(cap),"planned_enrollment":int(cap),
                                 "section_status":"PROPOSED"})
            if fid:
                wid=f"WLA-2026-{len(assignment_rows)+1:06d}"
                assignment_rows.append({"workload_assignment_id":wid,"section_id":sid,"faculty_id":fid,
                                         "weekly_hours":int(c.weekly_hours),"assignment_status":"PROPOSED"})
                fac_load[fid]+=int(c.weekly_hours)
            else:
                unmet_rows.append({"unmet_demand_id":make_id("UMD",len(unmet_rows)+1),"course_id":c.course_id,
                                   "term":config["target_term"],"unmet_students":int(cap),
                                   "reason":"NO_SKILLED_FACULTY_WITH_CAPACITY"})
            allocated+=cap
        if allocated<demand:
            unmet_rows.append({"unmet_demand_id":make_id("UMD",len(unmet_rows)+1),"course_id":c.course_id,
                               "term":config["target_term"],"unmet_students":int(demand-allocated),
                               "reason":"ROOM_OR_SECTION_CAPACITY_LIMIT"})

    sections=pd.DataFrame(section_rows,columns=["section_id","course_id","term","room_id","capacity","planned_enrollment","section_status"])
    workload=pd.DataFrame(assignment_rows,columns=["workload_assignment_id","section_id","faculty_id","weekly_hours","assignment_status"])
    unmet=pd.DataFrame(unmet_rows,columns=["unmet_demand_id","course_id","term","unmet_students","reason"])
    # Append-only lifecycle events for initial proposals (future approvals append new rows).
    event_rows=[]
    for _, row in sections.iterrows():
        event_rows.append({"event_id":len(event_rows)+1,"entity_type":"SECTION","entity_id":row.section_id,
                           "from_state":"","to_state":row.section_status,"event_time":"2026-06-01T09:00:00",
                           "actor_role":"ACADEMIC_ADMIN","reason":"Forecast-based section proposal"})
    for _, row in workload.iterrows():
        event_rows.append({"event_id":len(event_rows)+1,"entity_type":"WORKLOAD_ASSIGNMENT","entity_id":row.workload_assignment_id,
                           "from_state":"","to_state":row.assignment_status,"event_time":"2026-06-01T09:05:00",
                           "actor_role":"ACADEMIC_ADMIN","reason":"Constraint-checked faculty proposal"})
    state_events=pd.DataFrame(event_rows,columns=["event_id","entity_type","entity_id","from_state","to_state","event_time","actor_role","reason"])

    # 5. Labelled negative scenarios live in separate issue records; baseline tables stay valid.
    ground_truth=[]
    anomaly_fixtures=[]
    if config.get("inject_anomalies",True) and len(sections):
        first=sections.iloc[0]
        first_course=courses[courses.course_id==first.course_id].iloc[0]
        # Negative fixtures are explicit, isolated test cases. They do not corrupt baseline tables.
        scenarios=[
          ("ANOM-001","FACULTY_OUTSIDE_SKILL_SET",first.section_id,"ASSIGNMENT_SKILL_MISMATCH","HIGH","Assigned faculty lacks course.required_skill"),
          ("ANOM-002","WORKLOAD_EXCEEDED",first.section_id,"WORKLOAD_LIMIT_BREACH","HIGH","Proposed weekly hours exceed faculty weekly_workload_limit"),
          ("ANOM-003","SECTION_CAPACITY_TOO_LOW",first.section_id,"CAPACITY_SHORTFALL","MEDIUM","Forecast demand is greater than sum of section capacities"),
          ("ANOM-004","COURSE_BEFORE_PREREQUISITE",first.course_id,"PREREQUISITE_SEQUENCE_VIOLATION","HIGH","Course term precedes completion term of required course"),
          ("ANOM-005","DUPLICATE_SECTION_ASSIGNMENT",first.section_id,"DUPLICATE_FACULTY_SECTION_ASSIGNMENT","HIGH","Same faculty is assigned to same section more than once")
        ]
        for case_id,issue,entity,expected,severity,detail in scenarios:
            fixture_id=f"FIX-{case_id[-3:]}"
            anomaly_fixtures.append({"fixture_id":fixture_id,"case_id":case_id,"issue_type":issue,
                                    "entity_id":entity,"invalid_condition":detail,"baseline_corrupted":False})
            ground_truth.append({"case_id":case_id,"fixture_id":fixture_id,"issue_type":issue,"entity_id":entity,
                                 "expected_detection":expected,"severity":severity})
    ground_truth=pd.DataFrame(ground_truth,columns=["case_id","fixture_id","issue_type","entity_id","expected_detection","severity"])
    anomaly_fixtures=pd.DataFrame(anomaly_fixtures,columns=["fixture_id","case_id","issue_type","entity_id","invalid_condition","baseline_corrupted"])

    tables={"programs":programs,"courses":courses,"prerequisites":prerequisites,"student_plans":plans,
            "registration_interests":interests,"faculty":faculty,"faculty_skills":skills,
            "availability":availability,"rooms":rooms,"sections":sections,"workload_assignments":workload,
            "demand_forecast":forecast,"unmet_demand":unmet,"state_events":state_events,
            "anomaly_fixtures":anomaly_fixtures,"ground_truth":ground_truth}
    for name,df in tables.items():
        df.to_csv(out/f"{name}.csv",index=False)
        df.to_json(out/f"{name}.json",orient="records",indent=2)
    return tables

def validate(t):
    errors=[]
    def unique(name,key):
        if t[name][key].duplicated().any(): errors.append(f"{name}.{key} is not unique")
    for name,key in [("programs","program_id"),("courses","course_id"),("faculty","faculty_id"),
                     ("student_plans","student_plan_id"),("sections","section_id"),
                     ("rooms","room_id"),("workload_assignments","workload_assignment_id")]:
        unique(name,key)
    checks=[
      ("courses","program_id","programs","program_id"),
      ("student_plans","program_id","programs","program_id"),
      ("registration_interests","student_plan_id","student_plans","student_plan_id"),
      ("registration_interests","course_id","courses","course_id"),
      ("faculty_skills","faculty_id","faculty","faculty_id"),
      ("availability","faculty_id","faculty","faculty_id"),
      ("sections","course_id","courses","course_id"),
      ("sections","room_id","rooms","room_id"),
      ("workload_assignments","section_id","sections","section_id"),
      ("workload_assignments","faculty_id","faculty","faculty_id"),
      ("prerequisites","course_id","courses","course_id"),
      ("prerequisites","required_course_id","courses","course_id")]
    for a,ak,b,bk in checks:
        if len(t[a]) and not set(t[a][ak]).issubset(set(t[b][bk])): errors.append(f"FK failure: {a}.{ak} -> {b}.{bk}")
    if len(t["workload_assignments"]):
        loads=t["workload_assignments"].groupby("faculty_id").weekly_hours.sum()
        limits=t["faculty"].set_index("faculty_id").weekly_workload_limit
        # Assignment generator enforces workload; report any breaches.
        if any(loads > limits.reindex(loads.index)): errors.append("Faculty workload limit exceeded")
    if len(t["sections"]):
        room_caps=t["sections"].merge(t["rooms"][["room_id","capacity"]],on="room_id",suffixes=("_section","_room"))
        if any(room_caps.capacity_section>room_caps.capacity_room): errors.append("Section exceeds room capacity")
    if len(t["registration_interests"]) and not set(t["registration_interests"].interest_status).issubset({"CONFIRMED","WITHDRAWN"}):
        errors.append("Invalid interest status")
    return errors

def write_report(t, outdir):
    out=Path(outdir)
    errors=validate(t)
    metrics={
      "programs":len(t["programs"]),"courses":len(t["courses"]),"faculty":len(t["faculty"]),
      "student_plans":len(t["student_plans"]),"registration_interests":len(t["registration_interests"]),
      "sections_proposed":len(t["sections"]),"faculty_assignments":len(t["workload_assignments"]),
      "unmet_demand_students":int(t["unmet_demand"].unmet_students.sum()) if len(t["unmet_demand"]) else 0,
      "forecast_students":int(t["demand_forecast"].forecast_enrollment.sum()),
      "validation_errors":errors,"validation_status":"PASS" if not errors else "FAIL"
    }
    (out/"validation_summary.json").write_text(json.dumps(metrics,indent=2))
    (out/"source_manifest.json").write_text(json.dumps({
      "provenance":"Fully synthetic data generated locally; no personal or external source data used.",
      "seed":20261022,"generator":"src/planner.py","tables":list(t.keys())
    },indent=2))
    return metrics

def checksums(folder):
    result={}
    for p in sorted(Path(folder).glob("*.csv")):
        result[p.name]=hashlib.sha256(p.read_bytes()).hexdigest()
    return result

def main():
    parser=argparse.ArgumentParser(description="Synthetic academic demand forecasting and faculty allocation")
    parser.add_argument("--config",default="config.json")
    parser.add_argument("--out",default="data")
    args=parser.parse_args()
    cfg=json.loads(Path(args.config).read_text())
    tables=generate(cfg,args.out)
    metrics=write_report(tables,args.out)
    (Path(args.out)/"checksums.json").write_text(json.dumps(checksums(args.out),indent=2))
    print(json.dumps(metrics,indent=2))
    if metrics["validation_errors"]: raise SystemExit(1)

if __name__=="__main__":
    main()
