export interface ProjectSummaryDTO {
  id: string
  title: string
  institution?: string | null
  career?: string | null
  authorName?: string | null
  updatedAt: string
}

export interface RubricCriterionDTO {
  id: string
  code: string
  description: string
  points?: number | null
  status: 'covered' | 'pending' | 'needs_evidence'
  evidenceNeeded?: string | null
}

export interface DocumentSectionDTO {
  id: string
  title: string
  level: number
  contentHtml: string
  orderIndex: number
}

export interface MemoryItemDTO {
  id: string
  key: string
  value: string
  category: string
  updatedAt: string
}

export interface StudioProps {
  currentProject: ProjectSummaryDTO | null
  allProjects: ProjectSummaryDTO[]
  sections: DocumentSectionDTO[]
  rubricCriteria: RubricCriterionDTO[]
  memories: MemoryItemDTO[]
  aiModels: string[]
  selectedModel: string
}
