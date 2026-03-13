from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger

from api.auth import get_current_user
from api.models import NoteCreate, NoteResponse, NoteUpdate
from open_notebook.database.repository import ensure_record_id, repo_query
from open_notebook.domain.notebook import Note
from open_notebook.exceptions import InvalidInputError

router = APIRouter()


@router.get("/notes", response_model=List[NoteResponse])
async def get_notes(
    notebook_id: Optional[str] = Query(None, description="Filter by notebook ID"),
    current_user: dict = Depends(get_current_user),
):
    """Get notes owned by the current user, optionally filtered by notebook."""
    try:
        owner_id = ensure_record_id(current_user["uid"])
        is_admin = current_user.get("role") == "admin"
        owner_filter = "in.owner = $owner OR in.owner IS NONE" if is_admin else "in.owner = $owner"
        note_filter = "owner = $owner OR owner IS NONE" if is_admin else "owner = $owner"

        if notebook_id:
            from open_notebook.domain.notebook import Notebook
            notebook = await Notebook.get(notebook_id)
            if not notebook:
                raise HTTPException(status_code=404, detail="Notebook not found")

            rows = await repo_query(
                f"""
                SELECT in.updated as note_updated, in.* as note FROM artifact
                WHERE out = $nb_id AND ({owner_filter})
                ORDER BY note_updated DESC
                FETCH in
                """,
                {"nb_id": ensure_record_id(notebook_id), "owner": owner_id},
            )
            notes = [Note(**r["note"]) for r in rows if r.get("note")] if rows else []
        else:
            rows = await repo_query(
                f"SELECT * FROM note WHERE {note_filter} ORDER BY updated DESC",
                {"owner": owner_id},
            )
            notes = [Note(**r) for r in rows] if rows else []

        return [
            NoteResponse(
                id=note.id or "",
                title=note.title,
                content=note.content,
                note_type=note.note_type,
                created=str(note.created),
                updated=str(note.updated),
            )
            for note in notes
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching notes: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching notes: {str(e)}")


@router.post("/notes", response_model=NoteResponse)
async def create_note(
    note_data: NoteCreate,
    current_user: dict = Depends(get_current_user),
):
    """Create a new note."""
    try:
        title = note_data.title
        if not title and note_data.note_type == "ai" and note_data.content:
            from open_notebook.graphs.prompt import graph as prompt_graph
            prompt = "Based on the Note below, please provide a Title for this content, with max 15 words"
            result = await prompt_graph.ainvoke(
                {"input_text": note_data.content, "prompt": prompt}  # type: ignore[arg-type]
            )
            title = result.get("output", "Untitled Note")

        note_type: Optional[Literal["human", "ai"]] = None
        if note_data.note_type in ("human", "ai"):
            note_type = note_data.note_type  # type: ignore[assignment]
        elif note_data.note_type is not None:
            raise HTTPException(status_code=400, detail="note_type must be 'human' or 'ai'")

        new_note = Note(
            title=title,
            content=note_data.content,
            note_type=note_type,
            owner=current_user["uid"],
        )
        command_id = await new_note.save()

        if note_data.notebook_id:
            from open_notebook.domain.notebook import Notebook
            notebook = await Notebook.get(note_data.notebook_id)
            if not notebook:
                raise HTTPException(status_code=404, detail="Notebook not found")
            await new_note.add_to_notebook(note_data.notebook_id)

        return NoteResponse(
            id=new_note.id or "",
            title=new_note.title,
            content=new_note.content,
            note_type=new_note.note_type,
            created=str(new_note.created),
            updated=str(new_note.updated),
            command_id=str(command_id) if command_id else None,
        )
    except HTTPException:
        raise
    except InvalidInputError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating note: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating note: {str(e)}")


@router.get("/notes/{note_id}", response_model=NoteResponse)
async def get_note(
    note_id: str,
    current_user: dict = Depends(get_current_user),
):
    try:
        note = await Note.get(note_id)
        if not note:
            raise HTTPException(status_code=404, detail="Note not found")
        if note.owner and str(note.owner) != current_user["uid"]:
            raise HTTPException(status_code=403, detail="Access denied")
        return NoteResponse(
            id=note.id or "",
            title=note.title,
            content=note.content,
            note_type=note.note_type,
            created=str(note.created),
            updated=str(note.updated),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching note {note_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching note: {str(e)}")


@router.put("/notes/{note_id}", response_model=NoteResponse)
async def update_note(
    note_id: str,
    note_update: NoteUpdate,
    current_user: dict = Depends(get_current_user),
):
    try:
        note = await Note.get(note_id)
        if not note:
            raise HTTPException(status_code=404, detail="Note not found")

        if note_update.title is not None:
            note.title = note_update.title
        if note_update.content is not None:
            note.content = note_update.content
        if note_update.note_type is not None:
            if note_update.note_type in ("human", "ai"):
                note.note_type = note_update.note_type  # type: ignore[assignment]
            else:
                raise HTTPException(status_code=400, detail="note_type must be 'human' or 'ai'")

        command_id = await note.save()

        return NoteResponse(
            id=note.id or "",
            title=note.title,
            content=note.content,
            note_type=note.note_type,
            created=str(note.created),
            updated=str(note.updated),
            command_id=str(command_id) if command_id else None,
        )
    except HTTPException:
        raise
    except InvalidInputError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating note {note_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating note: {str(e)}")


@router.delete("/notes/{note_id}")
async def delete_note(
    note_id: str,
    current_user: dict = Depends(get_current_user),
):
    try:
        note = await Note.get(note_id)
        if not note:
            raise HTTPException(status_code=404, detail="Note not found")
        if note.owner and str(note.owner) != current_user["uid"]:
            raise HTTPException(status_code=403, detail="Access denied")
        await note.delete()
        return {"message": "Note deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting note {note_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting note: {str(e)}")
