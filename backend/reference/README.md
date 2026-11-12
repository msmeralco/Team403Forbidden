# Reference documents for inspection planning

Put the documents that should decide how inspections are ranked in this folder.

- **Formats:** Markdown (`.md`) or plain text (`.txt`).
- **Naming:** any file name. This `README.md` is ignored.
- **Writing them:** short sections under headings work best. Each section becomes one or more
  records of about 900 characters, and the heading is kept with every record so it can be found.

Nothing else is needed. The next time Liwa writes a plan, the files are read, split, embedded
and stored in the local vector database (`backend/.cache/firstlook.db`). Edit or delete a file and
its records follow. Liwa then retrieves the passages that fit the situation and Claude ranks the
inspections by them; guidance here takes priority over FirstLook's built-in rule.

Until there is a document here, the only reference is the built-in rule: safety first, then
essential facilities, then homes.
