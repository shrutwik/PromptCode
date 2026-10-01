# Vercel publication

Public URL: https://promptcode-pitch.vercel.app/
Project: shrutwiks-projects/promptcode-pitch

Build the static deployment folder with `node build-vercel.mjs` from this directory. Deploy from `vercel-public` with `vercel deploy --prod`. The linked project metadata is in the ignored `vercel-public/.vercel` folder. Do not delete that folder when rebuilding.

Only the site HTML, CSS, and JavaScript are published. PDF/PPT exports are unchanged and are not part of the Vercel site. Sites hosting remains separate.

The initial Vercel deployment completed successfully. The CLI attempted to connect the parent GitHub repository, but that connection failed; automatic deployments from GitHub are not configured. Future updates can be deployed from this workspace. Collaborator editing permissions have not been granted because no collaborators were specified.

Unauthenticated HTTP checks returned 200 and matched the local content for the landing, deck HTML, and all four CSS/JavaScript assets.
