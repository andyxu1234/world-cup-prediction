import { WebView } from '@tarojs/components'
import { useRouter } from '@tarojs/taro'

export default function WebViewPage() {
  const router = useRouter()
  const url = decodeURIComponent(router.params.url || '')

  return <WebView src={url} />
}
