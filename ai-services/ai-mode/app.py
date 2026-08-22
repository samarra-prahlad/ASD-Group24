from plan import PLAN
from act import act
from observe import observe_all_services
from adapt import human_review, adapt


def main():
    print("=" * 60)
    print("GROUP 24 SHARED AGENTIC LOOP")
    print("=" * 60)

    print()
    print("PLAN")
    print(PLAN)

    print()
    act()

    print()
    print("OBSERVE")
    results = observe_all_services(PLAN)

    print()
    print("Evidence collected:")
    for line in results:
        print(f"  {line}")

    print()
    decision = human_review()

    print()
    print(f"Decision: {decision}")
    adapt(decision)

    print()
    print("LOOP COMPLETE")


if __name__ == "__main__":
    main()