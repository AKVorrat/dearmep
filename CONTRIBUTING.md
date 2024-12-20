<!--
SPDX-FileCopyrightText: © 2024 Tim Weber

SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Contributing to DearMEP

**TODO:**
Right now, this file is focusing solely on copyright and licensing.
It should be extended to cover all aspects of contributing to the project, just like [a good `CONTRIBUTING.md` does](https://mozillascience.github.io/working-open-workshop/contributing/).


## Copyright and Licensing

DearMEP is a free software project distributed under the terms of the AGPL version 3 or later (see [`LICENSE.md`](LICENSE.md) for details).
By contributing to the project, you allow your contributions to be subject to these license terms as well.

Additionally, you certify that your contribution conforms to the terms of the [Developer Certificate of Origin, version 1.1](doc/dco.txt), which basically states that you have created your contribution yourself, and/or that you have the right to submit it and subject it to the terms of our software license.

### Signing Off Commits

To make your acknowledgement more explicit, we require you to [signoff](https://git-scm.com/docs/git-commit#Documentation/git-commit.txt---signoff) each commit by adding a line like this to the end of your commit message:

```
Signed-off-by: Your Name <yourname@example.org>
```

You can use the `-s` / `--signoff` option of `git commit` to create such a line automatically.

Commits without a signoff line will be rejected.

### Signing Off Automatically

Git does not have a configuration option to automatically signoff every commit you make to a repository.
Instead, if you don't want to add `-s` to every commit you make, you will either need to set up an [alias](https://git-scm.com/book/en/v2/Git-Basics-Git-Aliases) or configure a [template for commit messages](https://git-scm.com/docs/git-config#Documentation/git-config.txt-committemplate).

### Adding Licensing Information to Files

DearMEP conforms to the [REUSE](https://reuse.software/) specification to provide machine-readable licensing information.

All files either have one or more `SPDX-FileCopyrightText` markers, as well as a `SPDX-License-Identifier`, in the file itself, or in a separate `<filename>.license` file next to it.

If you create a new file, you will need to add this information yourself.
Either do it manually, using an existing file as a template for how to do it, or use the `reuse annotate` command of [the `reuse` tool](https://github.com/fsfe/reuse-tool) to do it for you.

If you contribute non-trivial additions or modifications to an existing file, you should add yourself to the list of copyright holders.
Again, you can either do that manually or using the `reuse` tool.

For example, after creating or modifying `foo.py`, if your name is not already listed in the file, you should run

```sh
reuse annotate -l AGPL-3.0-or-later --copyright-style spdx-symbol --copyright 'Your Name' foo.py
```

to create the necessary information.

**Notes:**

* You should not "bump" or update the year listed in the `FileCopyrightText` line next to your name. Set it to the current year when you make your first contribution and then leave it like that. (see [Why not bump the year on change?](https://www.openstreetmap.org/changeset/159670622))
* The format for `FileCopyrightText` that we're using is `ⓒ 2024 Your Name`, as generated by the `--copyright-style spdx-symbol` option of `reuse`.
* You don't have to use your legal name, a pseudonym or handle is okay, too. (see [What if I want to stay anonymous?](https://matija.suklje.name/how-and-why-to-properly-write-copyright-statements-in-your-code#what-if-i-want-to-stay-anonymous))
* If you use a code snippet, media file, etc. from somewhere else, with someone else's copyright and possibly some other license, use an [SPDX snippet](https://reuse.software/faq/#partial-license) to mark it accordingly.

You can always use `reuse lint` to check whether everything has been recognized correctly.
