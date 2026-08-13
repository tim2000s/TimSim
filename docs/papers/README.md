# The studies

Each file here is one piece of work, written so it can be read on its own: what was asked,
how it was measured, what came out, and what it means. They are separate from the reference
documents because a reference document says what is true now, and these say how it came to be
believed, including where the answer was the opposite of the one expected.

Most of these are negative. That is not an accident of presentation. Of the mechanisms and
explanations tested here, more were refused than adopted, and the ones that survived did so
after the first two or three candidates had been eliminated by measurement.

| # | Study | Question | Answer |
|---|---|---|---|
| 01 | [Driving shipped algorithms](01-shipped-algorithms.md) | Can the real code be run instead of a port of it? | Yes, for both Boost and oref0, and the port was costing 41% on dose |
| 02 | [The layer ladder under four drivers](02-layer-ladder.md) | Which layers change the person rather than the run? | Twelve of forty-seven movements; every layer carries something |
| 03 | [A statistic that could not see](03-drift-signature.md) | Does the ISF drift signature measure the person? | No. It reads the controller's own thermostat |
| 04 | [Sensitivity detection](04-autosens.md) | Does missing autosens explain oref0's hypoglycaemia? | No. Built it; nothing moved |
| 05 | [Where a low comes from](05-rescue-carbohydrate.md) | Why does the model rebound twice as often as real people? | Not the dose schedule, the carbohydrate response, or the treated share |
| 06 | [Four mechanisms for realism](06-four-mechanisms.md) | Can absorption spread, activity or slow sensitivity close the gaps? | One of four; and it works for the wrong reason |
| 07 | [A gap that was not there](07-meal-peak-timing.md) | Why do this model's meals peak 45 minutes early? | They do not. The two sides were clocked from different events |
| 08 | [No floor under a falling glucose](08-no-floor.md) | Why do runs fail to complete? | Glucose falls to zero. Nothing in the model arrests a fall |

## A note on sample sizes

Every real-data measurement made before 13 August drew on six to fourteen users, because the
file glob missed any name carrying a user-id prefix. One hundred and thirty-six users have
CGM. The affected measurements have been remade on thirty and the papers carry both sets where
they differ.

Three held: the response to rescue carbohydrate, the meal peak timing on both clocks, and the
within-person spread of meal absorption. Two moved: the size of a rescue helping, whose median
came down from 22 g to 15 g at 65 mg/dL, and the claim that treating a low shortens it, which
was an artefact of thirteen users and is not true of thirty.

## Reading them against the reference documents

[MODEL.md](../MODEL.md) describes UVA/Padova itself. [SIMULATOR.md](../SIMULATOR.md)
describes what this package puts on top. [CAPABILITY.md](../CAPABILITY.md) says what the
result can and cannot be used for, against the licensed releases and against real users.
[FIDELITY.md](../FIDELITY.md) and [LADDER.md](../LADDER.md) carry the measurements these
studies produced.
