def human_review():
    print()
    print("HUMAN REVIEW")
    print("1 - Accept")
    print("2 - Partially Accept")
    print("3 - Reject")

    decision = input("Decision: ").strip()

    if decision == "1":
        return "Accept"
    if decision == "2":
        return "Partially Accept"
    return "Reject"


def adapt(decision):
    print()
    if decision == "Accept":
        print("ADAPT: Apply recommendation and rerun validation.")
    elif decision == "Partially Accept":
        print("ADAPT: Apply selected recommendations and rerun validation.")
    else:
        print("ADAPT: Keep current implementation and document rationale.")