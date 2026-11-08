import { render, screen, fireEvent } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import { UserReviewForm } from '@/components/restaurant/UserReviewForm'
import { useReviewsStore } from '@/store/reviewsStore'

describe('UserReviewForm', () => {
  beforeEach(() => {
    localStorage.clear()
    useReviewsStore.setState({ reviews: [] })
  })

  it('exibe estrelas e campo de comentário', () => {
    render(
      <UserReviewForm restaurantId="r1" onReviewSubmitted={() => {}} />
    )

    expect(screen.getByLabelText('Avaliar de 1 a 5 estrelas')).toBeTruthy()
    expect(screen.getByPlaceholderText(/Conte o que achou/)).toBeTruthy()
    const submit = screen.getByRole('button', { name: /Enviar avaliação/ })
    expect(submit.getAttribute('disabled')).toBe('')
  })

  it('habilita o envio apenas com estrelas e comentário preenchidos', () => {
    render(
      <UserReviewForm restaurantId="r1" onReviewSubmitted={() => {}} />
    )

    const stars = screen.getAllByRole('button', { name: /Avaliar com/ })
    fireEvent.click(stars[3]) // 4 estrelas

    const comment = screen.getByPlaceholderText(/Conte o que achou/)
    fireEvent.change(comment, { target: { value: 'Gostei muito' } })

    const submit = screen.getByRole('button', { name: /Enviar avaliação/ })
    expect(submit.getAttribute('disabled')).toBeNull()
  })

  it('adiciona a avaliação na store ao submeter', () => {
    render(
      <UserReviewForm restaurantId="r1" onReviewSubmitted={() => {}} />
    )

    const stars = screen.getAllByRole('button', { name: /Avaliar com/ })
    fireEvent.click(stars[2]) // 3 estrelas

    const comment = screen.getByPlaceholderText(/Conte o que achou/)
    fireEvent.change(comment, { target: { value: 'Muito bom' } })

    fireEvent.click(screen.getByRole('button', { name: /Enviar avaliação/ }))

    const reviews = useReviewsStore.getState().getReviewsForRestaurant('r1')
    expect(reviews).toHaveLength(1)
    expect(reviews[0].rating).toBe(3)
    expect(reviews[0].comment).toBe('Muito bom')
  })
})
