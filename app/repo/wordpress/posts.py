"""
WordPress Posts, Comments, and Terms Repository.
Provides CRUD operations for core WordPress content types.
"""
from typing import List, Optional, Any
from datetime import datetime
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from app.model.wordpress.core import (
    WPPost, WPPostMeta, WPComment, WPCommentMeta,
    WPTerm, WPTermMeta, WPTermTaxonomy, WPTermRelationship
)
from app.schema.wordpress.post import (
    WPPostCreate, WPPostUpdate, WPPostRead, WPPostWithTerms,
    WPCommentCreate, WPCommentUpdate, WPCommentRead,
    WPCategory, WPTag, WPImageRead
)
from app.core.urls import rewrite_url


class WPPostRepository:
    """Repository for WordPress posts and pages"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_posts(
        self,
        post_type: str = "post",
        status: str = "publish",
        limit: int = 10,
        offset: int = 0
    ) -> List[WPPostRead]:
        """Get list of posts by type and status"""
        statement = select(WPPost).where(WPPost.post_type == post_type)

        if status != "any":
            statement = statement.where(WPPost.post_status == status)

        statement = statement.order_by(WPPost.post_date.desc()).limit(limit).offset(offset)
        result = await self.session.exec(statement)
        posts = result.all()

        post_reads = []
        for p in posts:
            p_read = WPPostRead(
                ID=p.ID,
                post_author=p.post_author,
                post_date=p.post_date,
                post_date_gmt=p.post_date_gmt,
                post_modified=p.post_modified,
                post_modified_gmt=p.post_modified_gmt,
                post_title=p.post_title,
                post_content=p.post_content,
                post_excerpt=p.post_excerpt,
                post_status=p.post_status,
                post_type=p.post_type,
                post_name=p.post_name,
                post_parent=p.post_parent,
                menu_order=p.menu_order,
                comment_status=p.comment_status,
                ping_status=p.ping_status,
                guid=p.guid,
                comment_count=p.comment_count
            )
            image_data = await self.get_featured_image(p.ID)
            if image_data:
                p_read.featured_image = WPImageRead(**image_data)
            post_reads.append(p_read)

        return post_reads

    async def get_post(self, post_id: int) -> Optional[WPPostRead]:
        """Get a single post by ID"""
        post = await self.session.get(WPPost, post_id)
        if not post:
            return None

        post_read = WPPostRead(
            ID=post.ID,
            post_author=post.post_author,
            post_date=post.post_date,
            post_date_gmt=post.post_date_gmt,
            post_modified=post.post_modified,
            post_modified_gmt=post.post_modified_gmt,
            post_title=post.post_title,
            post_content=post.post_content,
            post_excerpt=post.post_excerpt,
            post_status=post.post_status,
            post_type=post.post_type,
            post_name=post.post_name,
            post_parent=post.post_parent,
            menu_order=post.menu_order,
            comment_status=post.comment_status,
            ping_status=post.ping_status,
            guid=post.guid,
            comment_count=post.comment_count
        )
        image_data = await self.get_featured_image(post_id)
        if image_data:
            post_read.featured_image = WPImageRead(**image_data)
        return post_read

    async def get_post_with_terms(self, post_id: int) -> Optional[WPPostWithTerms]:
        """Get post with associated categories and tags"""
        post = await self.get_post(post_id)
        if not post:
            return None

        # Get categories
        categories = await self._get_post_terms(post_id, "category")

        # Get tags
        tags = await self._get_post_terms(post_id, "post_tag")

        # Get meta
        meta_stmt = select(WPPostMeta).where(WPPostMeta.post_id == post_id)
        meta_result = await self.session.exec(meta_stmt)
        meta = meta_result.all()

        return WPPostWithTerms(
            **post.model_dump(),
            categories=[
                WPCategory(
                    term_id=t["term_id"],
                    name=t["name"],
                    slug=t["slug"],
                    description=t.get("description", ""),
                    parent=t.get("parent", 0),
                    count=t.get("count", 0)
                ) for t in categories
            ],
            tags=[
                WPTag(
                    term_id=t["term_id"],
                    name=t["name"],
                    slug=t["slug"],
                    description=t.get("description", ""),
                    count=t.get("count", 0)
                ) for t in tags
            ],
            meta=[]  # Simplified for now
        )

    async def get_post_by_id(self, post_id: int, post_type: str = "post") -> Optional[WPPostRead]:
        """Get a single post by numeric ID"""
        statement = select(WPPost).where(
            WPPost.ID == post_id,
            WPPost.post_type == post_type,
        )
        result = await self.session.exec(statement)
        post = result.first()
        if not post:
            return None

        post_read = WPPostRead(
            ID=post.ID,
            post_author=post.post_author,
            post_date=post.post_date,
            post_date_gmt=post.post_date_gmt,
            post_modified=post.post_modified,
            post_modified_gmt=post.post_modified_gmt,
            post_title=post.post_title,
            post_content=post.post_content,
            post_excerpt=post.post_excerpt,
            post_status=post.post_status,
            post_type=post.post_type,
            post_name=post.post_name,
            post_parent=post.post_parent,
            menu_order=post.menu_order,
            comment_status=post.comment_status,
            ping_status=post.ping_status,
            guid=post.guid,
            comment_count=post.comment_count
        )
        image_data = await self.get_featured_image(post.ID)
        if image_data:
            post_read.featured_image = WPImageRead(**image_data)
        return post_read

    async def get_post_by_slug(self, slug: str, post_type: str = "post") -> Optional[WPPostRead]:
        """Get a single post by slug (post_name). Tries multiple formats to handle spaces vs dashes."""
        # Try multiple slug formats: as-is, with dashes, and with spaces
        slug_variants = list(dict.fromkeys([
            slug,
            slug.replace(" ", "-"),
            slug.replace("-", " "),
            slug.lower().replace(" ", "-"),
            slug.lower().replace("-", " "),
        ]))

        from sqlalchemy import or_
        statement = select(WPPost).where(
            or_(*[WPPost.post_name == v for v in slug_variants]),
            WPPost.post_type == post_type,
            WPPost.post_status == "publish"
        )
        result = await self.session.exec(statement)
        post = result.first()
        if not post:
            return None

        post_read = WPPostRead(
            ID=post.ID,
            post_author=post.post_author,
            post_date=post.post_date,
            post_date_gmt=post.post_date_gmt,
            post_modified=post.post_modified,
            post_modified_gmt=post.post_modified_gmt,
            post_title=post.post_title,
            post_content=post.post_content,
            post_excerpt=post.post_excerpt,
            post_status=post.post_status,
            post_type=post.post_type,
            post_name=post.post_name,
            post_parent=post.post_parent,
            menu_order=post.menu_order,
            comment_status=post.comment_status,
            ping_status=post.ping_status,
            guid=post.guid,
            comment_count=post.comment_count
        )
        image_data = await self.get_featured_image(post.ID)
        if image_data:
            post_read.featured_image = WPImageRead(**image_data)
        return post_read

    async def get_post_with_terms_by_slug(self, slug: str, post_type: str = "post") -> Optional[WPPostWithTerms]:
        """Get post with associated categories and tags by slug"""
        post = await self.get_post_by_slug(slug, post_type=post_type)
        if not post:
            return None

        post_id = post.ID

        # Get categories
        categories = await self._get_post_terms(post_id, "category")

        # Get tags
        tags = await self._get_post_terms(post_id, "post_tag")

        # Get meta
        meta_stmt = select(WPPostMeta).where(WPPostMeta.post_id == post_id)
        meta_result = await self.session.exec(meta_stmt)
        meta = meta_result.all()

        return WPPostWithTerms(
            **post.model_dump(),
            categories=[
                WPCategory(
                    term_id=t["term_id"],
                    name=t["name"],
                    slug=t["slug"],
                    description=t.get("description", ""),
                    parent=t.get("parent", 0),
                    count=t.get("count", 0)
                ) for t in categories
            ],
            tags=[
                WPTag(
                    term_id=t["term_id"],
                    name=t["name"],
                    slug=t["slug"],
                    description=t.get("description", ""),
                    count=t.get("count", 0)
                ) for t in tags
            ],
            meta=[]  # Simplified for now
        )

    async def _get_post_terms(self, post_id: int, taxonomy: str) -> List[dict]:
        """Get terms for a post by taxonomy"""
        stmt = (
            select(WPTerm, WPTermTaxonomy)
            .join(WPTermTaxonomy, WPTerm.term_id == WPTermTaxonomy.term_id)
            .join(WPTermRelationship, WPTermTaxonomy.term_taxonomy_id == WPTermRelationship.term_taxonomy_id)
            .where(
                WPTermRelationship.object_id == post_id,
                WPTermTaxonomy.taxonomy == taxonomy
            )
        )
        result = await self.session.exec(stmt)
        terms = result.all()

        return [
            {
                "term_id": term.term_id,
                "name": term.name,
                "slug": term.slug,
                "description": tax.description,
                "parent": tax.parent,
                "count": tax.count
            }
            for term, tax in terms
        ]

    async def create_post(self, user_id: int, data: WPPostCreate) -> WPPostRead:
        """Create a new post or page"""
        # Generate slug if not provided
        slug = data.post_name or data.post_title.lower().replace(" ", "-")

        new_post = WPPost(
            post_author=user_id,
            post_title=data.post_title,
            post_content=data.post_content or "",
            post_excerpt=data.post_excerpt or "",
            post_status=data.post_status or "draft",
            post_type=data.post_type or "post",
            post_name=slug,
            post_parent=data.post_parent or 0,
            menu_order=data.menu_order or 0,
            comment_status=data.comment_status or "open",
            ping_status=data.ping_status or "open",
            post_date=datetime.now(),
            post_date_gmt=datetime.now(),
            post_modified=datetime.now(),
            post_modified_gmt=datetime.now()
        )

        self.session.add(new_post)
        await self.session.commit()
        await self.session.refresh(new_post)

        post_id = new_post.ID

        return await self.get_post(post_id)

    async def update_post(self, post_id: int, data: WPPostUpdate) -> Optional[WPPostRead]:
        """Update an existing post"""
        post = await self.session.get(WPPost, post_id)
        if not post:
            return None

        # Update fields if provided
        if data.post_title is not None:
            post.post_title = data.post_title
        if data.post_content is not None:
            post.post_content = data.post_content
        if data.post_excerpt is not None:
            post.post_excerpt = data.post_excerpt
        if data.post_status is not None:
            post.post_status = data.post_status
        if data.post_name is not None:
            post.post_name = data.post_name
        if data.post_parent is not None:
            post.post_parent = data.post_parent
        if data.menu_order is not None:
            post.menu_order = data.menu_order
        if data.comment_status is not None:
            post.comment_status = data.comment_status
        if data.ping_status is not None:
            post.ping_status = data.ping_status

        post.post_modified = datetime.now()
        post.post_modified_gmt = datetime.now()

        self.session.add(post)
        await self.session.commit()

        return await self.get_post(post_id)

    async def delete_post(self, post_id: int, force: bool = False) -> bool:
        """Delete (trash) a post. If force=True, permanently delete."""
        post = await self.session.get(WPPost, post_id)
        if not post:
            return False

        if force:
            # Permanently delete
            await self.session.delete(post)
        else:
            # Move to trash
            post.post_status = "trash"
            self.session.add(post)

        await self.session.commit()
        return True

    async def get_post_meta(self, post_id: int, meta_key: Optional[str] = None) -> List[dict]:
        """Get post meta, optionally filtered by key"""
        stmt = select(WPPostMeta).where(WPPostMeta.post_id == post_id)
        if meta_key:
            stmt = stmt.where(WPPostMeta.meta_key == meta_key)

        result = await self.session.exec(stmt)
        return [{"meta_key": m.meta_key, "meta_value": m.meta_value} for m in result.all()]

    async def set_post_meta(self, post_id: int, meta_key: str, meta_value: str) -> None:
        """Set or update post meta"""
        stmt = select(WPPostMeta).where(
            WPPostMeta.post_id == post_id,
            WPPostMeta.meta_key == meta_key
        )
        result = await self.session.exec(stmt)
        meta = result.first()

        if meta:
            meta.meta_value = meta_value
            self.session.add(meta)
        else:
            new_meta = WPPostMeta(post_id=post_id, meta_key=meta_key, meta_value=meta_value)
            self.session.add(new_meta)

        await self.session.commit()

    # ============== Featured Image Methods ==============

    async def set_featured_image(self, post_id: int, attachment_id: int) -> bool:
        """Set featured image for a post using _thumbnail_id meta"""
        # Verify post exists
        post = await self.session.get(WPPost, post_id)
        if not post:
            return False

        # Verify attachment exists
        attachment = await self.session.get(WPPost, attachment_id)
        if not attachment or attachment.post_type != "attachment":
            return False

        # Set _thumbnail_id meta
        await self.set_post_meta(post_id, "_thumbnail_id", str(attachment_id))
        return True

    async def get_featured_image(self, post_id: int) -> Optional[dict]:
        """Get featured image details for a post"""
        # Get thumbnail ID from meta
        meta = await self.get_post_meta(post_id, "_thumbnail_id")
        if not meta or not meta[0].get("meta_value"):
            return None

        attachment_id = int(meta[0]["meta_value"])

        # Get attachment details
        attachment = await self.session.get(WPPost, attachment_id)
        if not attachment or attachment.post_type != "attachment":
            return None

        # Get alt text
        alt_stmt = select(WPPostMeta).where(
            WPPostMeta.post_id == attachment_id,
            WPPostMeta.meta_key == "_wp_attachment_alt_text"
        )
        alt_result = await self.session.exec(alt_stmt)
        alt_meta = alt_result.first()

        return {
            "id": attachment.ID,
            "title": attachment.post_title,
            "url": rewrite_url(attachment.guid),
            "alt_text": alt_meta.meta_value if alt_meta else "",
            "caption": attachment.post_excerpt
        }

    async def remove_featured_image(self, post_id: int) -> bool:
        """Remove featured image from a post"""
        stmt = select(WPPostMeta).where(
            WPPostMeta.post_id == post_id,
            WPPostMeta.meta_key == "_thumbnail_id"
        )
        result = await self.session.exec(stmt)
        meta = result.first()

        if meta:
            await self.session.delete(meta)
            await self.session.commit()
            return True
        return False

class WPCommentRepository:
    """Repository for WordPress comments"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_comments(
        self,
        post_id: Optional[int] = None,
        status: str = "approve",
        limit: int = 50,
        offset: int = 0
    ) -> List[WPCommentRead]:
        """Get comments, optionally filtered by post"""
        stmt = select(WPComment)

        if post_id:
            stmt = stmt.where(WPComment.comment_post_ID == post_id)

        # Map status to comment_approved value
        status_map = {"approve": "1", "hold": "0", "spam": "spam", "trash": "trash"}
        if status in status_map:
            stmt = stmt.where(WPComment.comment_approved == status_map[status])

        stmt = stmt.order_by(WPComment.comment_date.desc()).limit(limit).offset(offset)
        result = await self.session.exec(stmt)
        comments = result.all()

        return [
            WPCommentRead(
                comment_ID=c.comment_ID,
                comment_post_ID=c.comment_post_ID,
                comment_author=c.comment_author,
                comment_author_email=c.comment_author_email,
                comment_author_url=c.comment_author_url,
                comment_content=c.comment_content,
                comment_date=c.comment_date,
                comment_date_gmt=c.comment_date_gmt,
                comment_approved=c.comment_approved,
                comment_parent=c.comment_parent,
                user_id=c.user_id,
                comment_karma=c.comment_karma
            )
            for c in comments
        ]

    async def get_comment(self, comment_id: int) -> Optional[WPCommentRead]:
        """Get a single comment by ID"""
        comment = await self.session.get(WPComment, comment_id)
        if not comment:
            return None

        return WPCommentRead(
            comment_ID=comment.comment_ID,
            comment_post_ID=comment.comment_post_ID,
            comment_author=comment.comment_author,
            comment_author_email=comment.comment_author_email,
            comment_author_url=comment.comment_author_url,
            comment_content=comment.comment_content,
            comment_date=comment.comment_date,
            comment_date_gmt=comment.comment_date_gmt,
            comment_approved=comment.comment_approved,
            comment_parent=comment.comment_parent,
            user_id=comment.user_id,
            comment_karma=comment.comment_karma
        )

    async def create_comment(self, data: WPCommentCreate, ip: str = "", user_agent: str = "") -> WPCommentRead:
        """Create a new comment"""
        new_comment = WPComment(
            comment_post_ID=data.comment_post_ID,
            comment_author=data.comment_author or "",
            comment_author_email=data.comment_author_email or "",
            comment_author_url=data.comment_author_url or "",
            comment_author_IP=ip,
            comment_content=data.comment_content,
            comment_date=datetime.now(),
            comment_date_gmt=datetime.now(),
            comment_approved="1",  # Auto-approve, can be modified
            comment_agent=user_agent,
            comment_parent=data.comment_parent or 0,
            user_id=data.user_id or 0
        )

        self.session.add(new_comment)
        await self.session.commit()
        await self.session.refresh(new_comment)

        # Store comment_ID before next commit expires it
        comment_id = new_comment.comment_ID

        # Update comment count on post
        post = await self.session.get(WPPost, data.comment_post_ID)
        if post:
            post.comment_count += 1
            self.session.add(post)
            await self.session.commit()

        return await self.get_comment(comment_id)

    async def update_comment(self, comment_id: int, data: WPCommentUpdate) -> Optional[WPCommentRead]:
        """Update an existing comment"""
        comment = await self.session.get(WPComment, comment_id)
        if not comment:
            return None

        if data.comment_content is not None:
            comment.comment_content = data.comment_content
        if data.comment_approved is not None:
            comment.comment_approved = data.comment_approved

        self.session.add(comment)
        await self.session.commit()

        return await self.get_comment(comment_id)

    async def delete_comment(self, comment_id: int, force: bool = False) -> bool:
        """Delete a comment. If force=True, permanently delete."""
        comment = await self.session.get(WPComment, comment_id)
        if not comment:
            return False

        post_id = comment.comment_post_ID

        if force:
            await self.session.delete(comment)
        else:
            comment.comment_approved = "trash"
            self.session.add(comment)

        await self.session.commit()

        # Update comment count on post
        post = await self.session.get(WPPost, post_id)
        if post and post.comment_count > 0:
            post.comment_count -= 1
            self.session.add(post)
            await self.session.commit()

        return True


class WPTermRepository:
    """Repository for WordPress terms (categories, tags, etc.)"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_terms(
        self,
        taxonomy: str = "category",
        limit: int = 100,
        offset: int = 0
    ) -> List[dict]:
        """Get terms by taxonomy"""
        stmt = (
            select(WPTerm, WPTermTaxonomy)
            .join(WPTermTaxonomy, WPTerm.term_id == WPTermTaxonomy.term_id)
            .where(WPTermTaxonomy.taxonomy == taxonomy)
            .order_by(WPTerm.name)
            .limit(limit).offset(offset)
        )
        result = await self.session.exec(stmt)
        terms = result.all()

        return [
            {
                "term_id": term.term_id,
                "name": term.name,
                "slug": term.slug,
                "taxonomy": tax.taxonomy,
                "description": tax.description,
                "parent": tax.parent,
                "count": tax.count,
                "term_taxonomy_id": tax.term_taxonomy_id
            }
            for term, tax in terms
        ]

    async def get_term(self, term_id: int) -> Optional[dict]:
        """Get a single term by ID"""
        term = await self.session.get(WPTerm, term_id)
        if not term:
            return None

        # Get taxonomy info
        stmt = select(WPTermTaxonomy).where(WPTermTaxonomy.term_id == term_id)
        result = await self.session.exec(stmt)
        tax = result.first()

        return {
            "term_id": term.term_id,
            "name": term.name,
            "slug": term.slug,
            "taxonomy": tax.taxonomy if tax else "",
            "description": tax.description if tax else "",
            "parent": tax.parent if tax else 0,
            "count": tax.count if tax else 0,
            "term_taxonomy_id": tax.term_taxonomy_id if tax else None
        }

    async def create_term(
        self,
        name: str,
        taxonomy: str = "category",
        slug: Optional[str] = None,
        description: str = "",
        parent: int = 0
    ) -> dict:
        """Create a new term"""
        # Create term
        new_term = WPTerm(
            name=name,
            slug=slug or name.lower().replace(" ", "-"),
            term_group=0
        )
        self.session.add(new_term)
        await self.session.commit()
        await self.session.refresh(new_term)

        # Store term_id before next commit expires it
        term_id = new_term.term_id

        # Create term taxonomy
        new_taxonomy = WPTermTaxonomy(
            term_id=term_id,
            taxonomy=taxonomy,
            description=description,
            parent=parent,
            count=0
        )
        self.session.add(new_taxonomy)
        await self.session.commit()

        return await self.get_term(term_id)

    async def update_term(
        self,
        term_id: int,
        name: Optional[str] = None,
        slug: Optional[str] = None,
        description: Optional[str] = None,
        parent: Optional[int] = None
    ) -> Optional[dict]:
        """Update an existing term"""
        term = await self.session.get(WPTerm, term_id)
        if not term:
            return None

        if name is not None:
            term.name = name
        if slug is not None:
            term.slug = slug

        self.session.add(term)

        # Update taxonomy
        stmt = select(WPTermTaxonomy).where(WPTermTaxonomy.term_id == term_id)
        result = await self.session.exec(stmt)
        tax = result.first()

        if tax:
            if description is not None:
                tax.description = description
            if parent is not None:
                tax.parent = parent
            self.session.add(tax)

        await self.session.commit()
        return await self.get_term(term_id)

    async def delete_term(self, term_id: int) -> bool:
        """Delete a term and its taxonomy"""
        term = await self.session.get(WPTerm, term_id)
        if not term:
            return False

        # Delete taxonomy first
        stmt = select(WPTermTaxonomy).where(WPTermTaxonomy.term_id == term_id)
        result = await self.session.exec(stmt)
        tax = result.first()
        if tax:
            # Delete relationships
            rel_stmt = select(WPTermRelationship).where(
                WPTermRelationship.term_taxonomy_id == tax.term_taxonomy_id
            )
            rel_result = await self.session.exec(rel_stmt)
            for rel in rel_result.all():
                await self.session.delete(rel)

            await self.session.delete(tax)

        await self.session.delete(term)
        await self.session.commit()
        return True

    async def assign_terms_to_post(self, post_id: int, term_ids: List[int]) -> bool:
        """Assign terms to a post"""
        for term_id in term_ids:
            # Get term taxonomy ID
            stmt = select(WPTermTaxonomy).where(WPTermTaxonomy.term_id == term_id)
            result = await self.session.exec(stmt)
            tax = result.first()

            if tax:
                # Check if relationship already exists
                rel_stmt = select(WPTermRelationship).where(
                    WPTermRelationship.object_id == post_id,
                    WPTermRelationship.term_taxonomy_id == tax.term_taxonomy_id
                )
                rel_result = await self.session.exec(rel_stmt)
                existing = rel_result.first()

                if not existing:
                    new_rel = WPTermRelationship(
                        object_id=post_id,
                        term_taxonomy_id=tax.term_taxonomy_id,
                        term_order=0
                    )
                    self.session.add(new_rel)

                    # Update count
                    tax.count += 1
                    self.session.add(tax)

        await self.session.commit()
        return True

    async def remove_terms_from_post(self, post_id: int, term_ids: List[int]) -> bool:
        """Remove terms from a post"""
        for term_id in term_ids:
            stmt = select(WPTermTaxonomy).where(WPTermTaxonomy.term_id == term_id)
            result = await self.session.exec(stmt)
            tax = result.first()

            if tax:
                rel_stmt = select(WPTermRelationship).where(
                    WPTermRelationship.object_id == post_id,
                    WPTermRelationship.term_taxonomy_id == tax.term_taxonomy_id
                )
                rel_result = await self.session.exec(rel_stmt)
                rel = rel_result.first()

                if rel:
                    await self.session.delete(rel)

                    # Update count
                    if tax.count > 0:
                        tax.count -= 1
                    self.session.add(tax)

        await self.session.commit()
        return True
